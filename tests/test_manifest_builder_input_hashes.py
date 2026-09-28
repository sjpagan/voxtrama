"""build_manifest's per-step input_sha256 and reuse_key: read straight off the row.

Split from test_manifest_builder_model_provenance.py, which covers the
other five row-only fields. Same split as builder.py/step_info.py in src,
for the same size-limit reason. Neither value is ever recomputed here:
build_manifest never receives an ExecutionContext (see
manifest/step_info.py's own docstring for why that matters to
engine.reconcile_manifest, which rebuilds a manifest from rows alone).
"""

from __future__ import annotations

from datetime import UTC, datetime

from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.manifest.builder import build_manifest
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow


def _run() -> Run:
    return Run(
        id="r1",
        workflow_name="demo",
        workflow_version="1.0.0",
        state=JobState.RUNNING,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _workflow() -> Workflow:
    return Workflow(
        name="demo",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="transcribe", skill="transcribe", skill_version="1.0.0")],
    )


def test_a_steps_input_hashes_reach_the_manifest():
    row = RunStep(
        id="transcribe",
        run_id="r1",
        step_id="transcribe",
        skill="transcribe",
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=0,
        attempts=1,
        input_sha256="a" * 64,
        reuse_key="b" * 64,
    )

    manifest = build_manifest(_run(), [row], _workflow(), {}, None, None)

    step = manifest.steps[0]
    assert step.input_sha256 == "a" * 64
    assert step.reuse_key == "b" * 64


def test_a_step_written_before_migration_0015_reports_both_as_none():
    row = RunStep(
        id="transcribe",
        run_id="r1",
        step_id="transcribe",
        skill="transcribe",
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=0,
        attempts=1,
    )

    manifest = build_manifest(_run(), [row], _workflow(), {}, None, None)

    step = manifest.steps[0]
    assert step.input_sha256 is None
    assert step.reuse_key is None
