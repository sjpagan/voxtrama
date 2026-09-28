"""The manifest as engine.run writes it, end to end.

build_manifest's own behaviour is unit-tested in test_manifest_builder.py
and test_manifest_sections.py. This file drives it through execute_run, the
way `voxtrama run`'s worker does, and reads the file back from disk.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill


def _workflow(*steps: Step) -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=list(steps),
    )


def _fake_skill(name: str) -> Skill:
    return Skill(
        name=name,
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=ModelClass.EXTRACTIVE,
        minimum_model_profile=ModelProfile.LOW,
        evidence_required=False,
        minimum_confidence=0.0,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )


def _recording(session: Session, duration_seconds: float) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=duration_seconds,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def _install(monkeypatch: pytest.MonkeyPatch, steps: dict) -> None:
    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", steps)
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {name: {"1.0.0": _fake_skill(name)} for name in steps}
    )


def test_manifest_exists_and_validates_after_a_successful_run(db_session: Session) -> None:
    created = create_run(db_session, "test-workflow", "unpinned")
    run = execute_run(db_session, created.id, workflow=_workflow())

    manifest = _read_manifest(run.id)

    assert manifest.run.final is True
    assert manifest.run.state == "succeeded"


def test_mid_run_the_manifest_already_exists_and_is_not_final(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed = {}

    def _check_mid_run(ctx: ExecutionContext) -> dict:
        manifest = _read_manifest(ctx.run.id)
        observed["final"] = manifest.run.final
        observed["states"] = [step.state for step in manifest.steps]
        return {}

    _install(monkeypatch, {"transcribe": _check_mid_run})
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="transcribe", skill="transcribe", skill_version="1.0.0")

    execute_run(db_session, created.id, workflow=_workflow(step))

    assert observed == {"final": False, "states": ["pending"]}


def test_a_failed_runs_manifest_has_failure_and_pending_steps(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(ctx: ExecutionContext) -> dict:
        raise RuntimeError("step exploded")

    _install(monkeypatch, {"first": _boom, "second": lambda ctx: {}})
    created = create_run(db_session, "test-workflow", "unpinned")
    workflow = _workflow(
        Step(id="first", skill="first", skill_version="1.0.0"),
        Step(id="second", skill="second", skill_version="1.0.0", depends_on=["first"]),
    )

    run = execute_run(db_session, created.id, workflow=workflow)

    manifest = _read_manifest(run.id)
    assert manifest.run.final is True
    assert manifest.failure is not None
    assert (manifest.failure.step, manifest.failure.message) == ("first", "step exploded")
    assert [step.state for step in manifest.steps] == ["failed", "pending"]


def test_a_skipped_step_appears_as_skipped_in_the_manifest(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, {"transcribe": lambda ctx: {}, "flag": lambda ctx: {}})
    recording = _recording(db_session, duration_seconds=120.0)
    created = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    workflow = _workflow(
        Step(id="transcribe", skill="transcribe", skill_version="1.0.0"),
        Step(
            id="flag",
            skill="flag",
            skill_version="1.0.0",
            depends_on=["transcribe"],
            condition="recording.duration_seconds < 10",
        ),
    )

    run = execute_run(db_session, created.id, workflow=workflow)

    manifest = _read_manifest(run.id)
    assert [step.state for step in manifest.steps] == ["succeeded", "skipped"]
