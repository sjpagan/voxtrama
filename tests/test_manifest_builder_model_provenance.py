"""build_manifest's per-step provenance: model, revision, provider, host, profile check.

Split from test_manifest_builder_step_output.py, which covers duration and
output hash. Same split as builder.py/step_info.py in src, kept apart
so neither test file grows past the project's size limit. Reads straight off
RunStep's own columns, never off an ExecutionContext: build_manifest never
receives one (see manifest/step_info.py's docstring for why that matters
to engine.reconcile_manifest).
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
        steps=[Step(id="summarize", skill="summarize", skill_version="1.0.0")],
    )


def test_a_generative_steps_provenance_reaches_the_manifest():
    row = RunStep(
        id="summarize",
        run_id="r1",
        step_id="summarize",
        skill="summarize",
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=0,
        attempts=1,
        model="qwen-test",
        model_revision="sha256:x",
        provider="ollama",
        host="127.0.0.1:11434",
        profile_check_skipped=False,
    )

    manifest = build_manifest(_run(), [row], _workflow(), {}, None, None)

    step = manifest.steps[0]
    assert step.model == "qwen-test"
    assert step.model_revision == "sha256:x"
    assert step.provider == "ollama"
    assert step.host == "127.0.0.1:11434"
    assert step.profile_check_skipped is False


def test_a_step_with_no_provenance_written_reports_all_five_as_none():
    """A pre-0013 row: every built-in today (transcribe, diarize, every
    generative step) calls record_provenance, so this is the only case
    left where all five read None.
    """
    row = RunStep(
        id="summarize",
        run_id="r1",
        step_id="summarize",
        skill="summarize",
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=0,
        attempts=1,
    )

    manifest = build_manifest(_run(), [row], _workflow(), {}, None, None)

    step = manifest.steps[0]
    assert (step.model, step.model_revision, step.provider, step.host) == (None, None, None, None)
    assert step.profile_check_skipped is None


def test_profile_check_skipped_none_and_false_are_not_conflated():
    """RunStep.profile_check_skipped's own rule: None is 'unknown', False is 'it ran'."""
    checked = RunStep(
        id="a",
        run_id="r1",
        step_id="a",
        skill="summarize",
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=0,
        attempts=1,
        profile_check_skipped=False,
    )
    unknown = RunStep(
        id="b",
        run_id="r1",
        step_id="a",
        skill="summarize",
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=1,
        attempts=1,
        profile_check_skipped=None,
    )

    manifest = build_manifest(_run(), [checked], _workflow(), {}, None, None)
    assert manifest.steps[0].profile_check_skipped is False

    manifest = build_manifest(_run(), [unknown], _workflow(), {}, None, None)
    assert manifest.steps[0].profile_check_skipped is None
