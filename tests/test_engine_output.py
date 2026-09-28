"""output.json as engine.run writes it, on a successful run.

Split from test_engine_output_failure.py, which covers the same file on a
run that fails: the same split as test_engine_manifest.py would need if it
grew past the test suite's own size limit. write_run_output and
read_run_output are unit-tested on their own in test_manifest_output.py.
This file drives them through execute_run, the way test_engine_manifest.py
drives the manifest, and reads output.json back from disk (never through
ExecutionContext.produced), the way a reader opening the run's folder after
the process has exited would.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.output import output_path
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path, sha256_of_file
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


def _skill(name: str, model_class: ModelClass = ModelClass.EXTRACTIVE) -> Skill:
    return Skill(
        name=name,
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=model_class,
        minimum_model_profile=ModelProfile.LOW,
        evidence_required=False,
        minimum_confidence=0.0,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )


def _install(
    monkeypatch: pytest.MonkeyPatch, steps: dict, model_class: ModelClass = ModelClass.EXTRACTIVE
) -> None:
    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", steps)
    monkeypatch.setattr(
        engine_run,
        "BUILTIN_SKILLS",
        {name: {"1.0.0": _skill(name, model_class)} for name in steps},
    )


def _runs_dir():
    return get_paths(get_settings().data_dir).runs_dir


def _read_manifest(run_id: str) -> Manifest:
    return Manifest.model_validate_json(manifest_path(_runs_dir(), run_id).read_text())


def test_a_finished_runs_output_holds_what_its_step_produced(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, {"summarize": lambda ctx: {"summary": "it happened"}})
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")

    run = execute_run(db_session, created.id, workflow=_workflow(step))

    payload = json.loads(output_path(_runs_dir(), run.id).read_bytes())
    assert payload["steps"]["summarize"] == {"summary": "it happened"}


def test_output_on_disk_carries_the_claim_and_its_anchored_evidence(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read straight off disk, never through ExecutionContext.produced."""

    def _summarize(ctx: ExecutionContext) -> dict:
        transcript = Transcript(
            id="t1",
            recording_id="r1",
            language="en",
            model_name="whisper",
            model_revision="v1",
            hardware_profile="low",
        )
        transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1.0)]
        ctx.transcript = transcript
        return {"claim": {"quote": "hello there"}}

    _install(monkeypatch, {"summarize": _summarize}, model_class=ModelClass.GENERATIVE)
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")

    run = execute_run(db_session, created.id, workflow=_workflow(step))

    payload = json.loads(output_path(_runs_dir(), run.id).read_bytes())
    claim = payload["steps"]["summarize"]["claim"]
    assert claim["quote"] == "hello there"
    assert claim["evidence"] == {"start": 0.0, "end": 2.0}
    assert claim["needs_review"] is False


def test_manifest_outputs_entry_matches_the_output_file_hash(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, {"summarize": lambda ctx: {"summary": "it happened"}})
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")

    run = execute_run(db_session, created.id, workflow=_workflow(step))

    manifest = _read_manifest(run.id)
    assert manifest.outputs[0].path == "output.json"
    assert manifest.outputs[0].sha256 == sha256_of_file(output_path(_runs_dir(), run.id))
