"""Tests for engine.validation: a step's output against its own skill's schema.

A run whose step returns something its own output_schema forbids must
fail loudly, naming the error code and the step.
It must never degrade into a result that looks complete and is not.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
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


def _skill_requiring_a_number() -> Skill:
    return Skill(
        name="fake",
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {"score": {"type": "number"}},
            "required": ["score"],
        },
        model_class=ModelClass.EXTRACTIVE,
        minimum_model_profile=ModelProfile.LOW,
        evidence_required=False,
        minimum_confidence=0.0,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )


def test_a_step_whose_output_violates_its_own_schema_fails_the_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _wrong_shape(ctx: ExecutionContext) -> dict:
        return {"score": "not a number"}

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"fake": _wrong_shape})
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {"fake": {"1.0.0": _skill_requiring_a_number()}}
    )

    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="score_it", skill="fake", skill_version="1.0.0")
    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.FAILED
    assert run.error_code == "output_schema_violation"
    assert run.error_step == "score_it"
