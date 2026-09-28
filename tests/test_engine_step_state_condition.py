"""A real run reads steps.<id>.state, not a fake context.

Grammar-level parsing and the loader's literal/operator/collision checks live
in test_workflow_condition_loader.py, and unit-level resolution in
test_engine_condition.py. This is the shape that only shows up once the
engine executes steps in order: a fallback that recovers a failed
step, and a condition that runs before the step it names has finished.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext, StepFunction
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import OnError, Step, Workflow
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


def _steps_of(session: Session, run_id: str) -> dict[str, RunStep]:
    rows = session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
    return {row.step_id: row for row in rows}


def _patch_builtins(monkeypatch: pytest.MonkeyPatch, steps: dict[str, StepFunction]) -> None:
    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", steps)
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {name: {"1.0.0": _fake_skill(name)} for name in steps}
    )


def test_a_step_recovered_by_its_fallback_still_reads_as_failed_to_a_later_condition(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case depends_on cannot express, and the reason this condition exists."""

    def _extract(ctx: ExecutionContext) -> dict:
        raise RuntimeError("extraction failed")

    def _no_op(ctx: ExecutionContext) -> dict:
        return {}

    _patch_builtins(monkeypatch, {"extract": _extract, "recover": _no_op, "flag": _no_op})

    created = create_run(db_session, "test-workflow", "unpinned")
    workflow = _workflow(
        Step(
            id="extract",
            skill="extract",
            skill_version="1.0.0",
            on_error=OnError(fallback_step="recover"),
        ),
        Step(id="recover", skill="recover", skill_version="1.0.0"),
        Step(
            id="flag",
            skill="flag",
            skill_version="1.0.0",
            depends_on=["extract"],
            condition='steps.extract.state == "failed"',
        ),
    )

    run = execute_run(db_session, created.id, workflow=workflow)

    assert run.state == JobState.SUCCEEDED
    rows = _steps_of(db_session, run.id)
    assert rows["extract"].state == StepState.FAILED
    assert rows["recover"].state == StepState.SUCCEEDED
    assert rows["flag"].state == StepState.SUCCEEDED


def test_a_condition_on_a_step_that_has_not_run_yet_fails_the_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """steps.<id>.state on a pending step is not a legitimate condition.

    ConditionEvaluationError here used to leave execute_run uncaught and
    the run stuck at `running` forever. Now it is an engine fault that
    closes the run, the same way an unhandled step failure already did.
    """

    def _no_op(ctx: ExecutionContext) -> dict:
        return {}

    _patch_builtins(monkeypatch, {"flag": _no_op, "later": _no_op})

    created = create_run(db_session, "test-workflow", "unpinned")
    workflow = _workflow(
        Step(
            id="flag",
            skill="flag",
            skill_version="1.0.0",
            condition='steps.later.state == "succeeded"',
        ),
        Step(id="later", skill="later", skill_version="1.0.0"),
    )

    run = execute_run(db_session, created.id, workflow=workflow)

    assert run.state == JobState.FAILED
    assert run.error_code == "internal"
    assert run.error_step == "flag"
