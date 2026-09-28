"""engine.preparation's wiring of anchor_output into execute_step.

Drives anchoring through execute_run, the way engine.run's worker does,
following the pattern of test_engine_validation.py: BUILTIN_STEPS and
BUILTIN_SKILLS monkeypatched, a fake step that builds its own Transcript
by hand and assigns it to ctx.transcript. No models, no audio.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.queue.job import JobState
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


def _skill(evidence_required: bool) -> Skill:
    return Skill(
        name="summarize",
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=ModelClass.GENERATIVE,
        minimum_model_profile=ModelProfile.LOW,
        evidence_required=evidence_required,
        minimum_confidence=0.0,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )


def _transcript() -> Transcript:
    transcript = Transcript(
        id="t1",
        recording_id="r1",
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="low",
    )
    transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1.0)]
    return transcript


def _install(monkeypatch: pytest.MonkeyPatch, output: dict, evidence_required: bool) -> None:
    def _run(ctx: ExecutionContext) -> dict:
        ctx.transcript = _transcript()
        return output

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"summarize": _run})
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {"summarize": {"1.0.0": _skill(evidence_required)}}
    )


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def test_missing_evidence_does_not_fail_the_run_when_not_required(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = {"claim": {"quote": "nowhere in the transcript"}}
    _install(monkeypatch, output, False)
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")

    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.SUCCEEDED
    assert output["claim"]["needs_review"] is True
    assert output["claim"]["evidence"] is None


def test_evidence_required_fails_the_run_when_a_claim_does_not_anchor(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, {"claim": {"quote": "nowhere in the transcript"}}, True)
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")

    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.FAILED
    assert run.error_code == "evidence_not_anchored"
    assert run.error_step == "summarize"


def test_the_failed_runs_manifest_still_counts_the_unanchored_claim(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, {"claim": {"quote": "nowhere in the transcript"}}, True)
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")

    run = execute_run(db_session, created.id, workflow=_workflow(step))

    manifest = _read_manifest(run.id)
    assert (manifest.evidence.claims, manifest.evidence.needs_review) == (1, 1)


def test_a_successful_runs_manifest_counts_an_anchored_claim(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, {"claim": {"quote": "hello there"}}, False)
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")

    run = execute_run(db_session, created.id, workflow=_workflow(step))

    manifest = _read_manifest(run.id)
    assert run.state == JobState.SUCCEEDED
    assert (manifest.evidence.claims, manifest.evidence.needs_review) == (1, 0)
