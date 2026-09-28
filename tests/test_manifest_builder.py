"""build_manifest's per-step section: deterministic, state, failure.

Split from test_manifest_sections.py, which covers the run-level sections
(languages, input). Same split as builder.py/sections.py in src, and
for the same reason: each file stays under the test suite's own size limit.
Complements test_engine_manifest.py, which drives the same shape through
execute_run end to end. steps[].duration_seconds and .output_sha256
are covered in test_manifest_builder_step_output.py instead, split off for
the same reason this file was.
"""

from __future__ import annotations

from datetime import UTC, datetime

from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.manifest.builder import build_manifest
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.skill import Determinism, ModelClass, ModelProfile, Privacy, Skill


def _run(state: JobState = JobState.RUNNING, **overrides) -> Run:
    defaults = dict(
        id="r1",
        workflow_name="demo",
        workflow_version="1.0.0",
        state=state,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return Run(**{**defaults, **overrides})


def _row(step_id: str, skill: str, state: StepState, position: int = 0) -> RunStep:
    return RunStep(
        id=step_id,
        run_id="r1",
        step_id=step_id,
        skill=skill,
        skill_version="1.0.0",
        state=state,
        position=position,
        attempts=1,
    )


def _skill(name: str, model_class: ModelClass) -> Skill:
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


def _workflow() -> Workflow:
    return Workflow(
        name="demo",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="transcribe", skill="transcribe", skill_version="1.0.0")],
    )


def test_deterministic_follows_an_extractive_skill():
    skills = {"transcribe": {"1.0.0": _skill("transcribe", ModelClass.EXTRACTIVE)}}
    row = _row("transcribe", "transcribe", StepState.SUCCEEDED)

    manifest = build_manifest(_run(), [row], _workflow(), skills, None, None)

    assert manifest.steps[0].deterministic == Determinism.SAME_HOST


def test_deterministic_follows_a_generative_skill():
    skills = {"summarize": {"1.0.0": _skill("summarize", ModelClass.GENERATIVE)}}
    row = _row("summarize", "summarize", StepState.SUCCEEDED)

    manifest = build_manifest(_run(), [row], _workflow(), skills, None, None)

    assert manifest.steps[0].deterministic == Determinism.NON_DETERMINISTIC


def test_a_skipped_step_is_reported_as_skipped():
    row = _row("flag", "flag", StepState.SKIPPED)

    manifest = build_manifest(_run(), [row], _workflow(), {}, None, None)

    assert manifest.steps[0].state == "skipped"


def test_failure_reports_code_message_and_step_while_the_next_stays_pending():
    run = _run(state=JobState.FAILED, error="boom", error_code="internal", error_step="transcribe")
    rows = [
        _row("transcribe", "transcribe", StepState.FAILED, position=0),
        _row("diarize", "diarize", StepState.PENDING, position=1),
    ]

    manifest = build_manifest(run, rows, _workflow(), {}, None, None)

    assert manifest.failure is not None
    assert (manifest.failure.code, manifest.failure.message, manifest.failure.step) == (
        "internal",
        "boom",
        "transcribe",
    )
    assert [step.state for step in manifest.steps] == ["failed", "pending"]
