"""Tests for on_error.retry and on_error.fallback_step, and the generative-retry veto.

Split from test_engine_run.py for the same reason test_engine_run_timeout.py
is: one topic each, kept under the file-length threshold that already
governs this test suite.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import OnError, RetryPolicy, Step, Workflow
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill


def _workflow(*steps: Step) -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=list(steps),
    )


def _steps_of(session: Session, run_id: str) -> dict[str, RunStep]:
    rows = session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
    return {row.step_id: row for row in rows}


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


def test_an_extractive_step_that_fails_twice_then_succeeds_records_three_attempts(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"count": 0}

    def _flaky(ctx: ExecutionContext) -> dict:
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError(f"attempt {calls['count']} failed")
        return {}

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"fake": _flaky})
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {"fake": {"1.0.0": _skill("fake", ModelClass.EXTRACTIVE)}}
    )

    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(
        id="only",
        skill="fake",
        skill_version="1.0.0",
        on_error=OnError(retry=RetryPolicy(max_attempts=2)),
    )
    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.SUCCEEDED
    assert calls["count"] == 3
    assert _steps_of(db_session, run.id)["only"].attempts == 3


def test_a_generative_step_is_never_retried_even_with_max_attempts_declared(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retrying is forbidden for a generative step that may already have
    produced something, whatever the workflow declares. This is the test
    that would catch a regression on that veto.
    """
    calls = {"count": 0}

    def _always_fails(ctx: ExecutionContext) -> dict:
        calls["count"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"fake": _always_fails})
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {"fake": {"1.0.0": _skill("fake", ModelClass.GENERATIVE)}}
    )

    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(
        id="only",
        skill="fake",
        skill_version="1.0.0",
        on_error=OnError(retry=RetryPolicy(max_attempts=2)),
    )
    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.FAILED
    assert calls["count"] == 1, "a generative step may not be retried, regardless of max_attempts"
    assert _steps_of(db_session, run.id)["only"].attempts == 1


def test_a_failed_step_recovers_through_its_declared_fallback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _primary(ctx: ExecutionContext) -> dict:
        raise RuntimeError("primary failed")

    def _fallback(ctx: ExecutionContext) -> dict:
        return {}

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"fake": _primary, "fake-rescue": _fallback})
    monkeypatch.setattr(
        engine_run,
        "BUILTIN_SKILLS",
        {
            "fake": {"1.0.0": _skill("fake", ModelClass.EXTRACTIVE)},
            "fake-rescue": {"1.0.0": _skill("fake-rescue", ModelClass.EXTRACTIVE)},
        },
    )

    created = create_run(db_session, "test-workflow", "unpinned")
    primary = Step(
        id="primary",
        skill="fake",
        skill_version="1.0.0",
        on_error=OnError(fallback_step="rescue"),
    )
    fallback = Step(id="rescue", skill="fake-rescue", skill_version="1.0.0")
    run = execute_run(db_session, created.id, workflow=_workflow(primary, fallback))

    assert run.state == JobState.SUCCEEDED
    rows = _steps_of(db_session, run.id)
    assert rows["primary"].state == StepState.FAILED
    assert rows["rescue"].state == StepState.SUCCEEDED
