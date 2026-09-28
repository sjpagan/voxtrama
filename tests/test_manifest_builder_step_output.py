"""build_manifest's per-step section: duration_seconds and output_sha256.

Split from test_manifest_builder.py, which covers the rest of steps[]
(deterministic, state, failure). Same split as builder.py/sections.py
in src, and for the same reason: each file stays under the test suite's own
size limit.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.manifest.builder import build_manifest
from voxtrama.manifest.jsonfile import serialize
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow


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


def _workflow() -> Workflow:
    return Workflow(
        name="demo",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="transcribe", skill="transcribe", skill_version="1.0.0")],
    )


def test_a_step_with_both_timestamps_reports_its_duration():
    row = _row("transcribe", "transcribe", StepState.SUCCEEDED)
    row.started_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    row.finished_at = datetime(2026, 1, 1, 0, 0, 1, 500000, tzinfo=UTC)

    manifest = build_manifest(_run(), [row], _workflow(), {}, None, None)

    assert manifest.steps[0].duration_seconds == 1.5


def test_a_step_missing_a_timestamp_has_no_duration():
    row = _row("transcribe", "transcribe", StepState.RUNNING)
    row.started_at = datetime(2026, 1, 1, tzinfo=UTC)
    row.finished_at = None

    manifest = build_manifest(_run(), [row], _workflow(), {}, None, None)

    assert manifest.steps[0].duration_seconds is None


def test_a_step_that_produced_something_has_its_output_hashed():
    row = _row("transcribe", "transcribe", StepState.SUCCEEDED)
    produced = {"transcribe": {"text": "hello"}}

    manifest = build_manifest(_run(), [row], _workflow(), {}, None, None, produced=produced)

    expected = hashlib.sha256(serialize(produced["transcribe"])).hexdigest()
    assert manifest.steps[0].output_sha256 == expected


def test_a_step_that_produced_nothing_has_no_output_hash():
    row = _row("flag", "flag", StepState.SKIPPED)

    manifest = build_manifest(_run(), [row], _workflow(), {}, None, None, produced={})

    assert manifest.steps[0].output_sha256 is None
