"""Tests for voxtrama.engine.run: create_run, and a workflow executed step by step."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.step import RunStep
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow


def _workflow(*steps: Step) -> Workflow:
    return Workflow(
        name="test-workflow",
        version="2.1.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=list(steps),
    )


def _step(step_id: str, skill: str, depends_on: list[str] | None = None) -> Step:
    return Step(id=step_id, skill=skill, skill_version="1.0.0", depends_on=depends_on or [])


def _steps_of(session: Session, run_id: str) -> list[RunStep]:
    rows = session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
    return sorted(rows, key=lambda row: row.position)


def test_create_run_starts_pending(db_session: Session) -> None:
    run = create_run(db_session, "demo-workflow", "1.0.0")
    assert run.id is not None
    assert run.state == JobState.PENDING
    assert run.started_at is None


def test_execute_run_raises_for_unknown_run_id(db_session: Session) -> None:
    with pytest.raises(ValueError):
        execute_run(db_session, "does-not-exist")


def test_a_workflow_without_steps_succeeds(db_session: Session) -> None:
    created = create_run(db_session, "test-workflow", "unpinned")
    run = execute_run(db_session, created.id, workflow=_workflow())
    assert run.state == JobState.SUCCEEDED
    assert run.started_at is not None and run.finished_at is not None
    assert run.error is None


def test_every_step_is_recorded_with_its_position_and_state(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    executed: list[str] = []

    # Real skill names, not "alpha"/"beta": a step's return value is now
    # validated against its skill's own output_schema, and reusing
    # the two built-in declarations is simpler than fabricating one.
    def _transcribe(ctx: ExecutionContext) -> dict:
        executed.append("alpha")
        return {"transcript_id": "t1"}

    def _diarize(ctx: ExecutionContext) -> dict:
        executed.append("beta")
        return {"transcript_id": "t1", "speaker_estimate": 2}

    monkeypatch.setattr(
        engine_run, "BUILTIN_STEPS", {"transcribe": _transcribe, "diarize": _diarize}
    )
    created = create_run(db_session, "test-workflow", "unpinned")

    run = execute_run(
        db_session,
        created.id,
        workflow=_workflow(_step("second", "diarize", ["first"]), _step("first", "transcribe")),
    )

    assert run.state == JobState.SUCCEEDED
    assert executed == ["alpha", "beta"]
    rows = _steps_of(db_session, run.id)
    assert [row.step_id for row in rows] == ["first", "second"]
    assert [row.state for row in rows] == [JobState.SUCCEEDED, JobState.SUCCEEDED]
    assert all(row.started_at is not None and row.finished_at is not None for row in rows)


def test_the_executed_workflow_version_replaces_the_unpinned_placeholder(
    db_session: Session,
) -> None:
    created = create_run(db_session, "test-workflow", "unpinned")
    run = execute_run(db_session, created.id, workflow=_workflow())
    assert run.workflow_version == "2.1.0"


def test_a_failing_step_stops_the_run_and_leaves_the_next_one_untouched(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(ctx: ExecutionContext) -> None:
        raise RuntimeError("step exploded")

    reached: list[str] = []
    monkeypatch.setattr(
        engine_run,
        "BUILTIN_STEPS",
        {"alpha": _boom, "beta": lambda ctx: reached.append("beta")},
    )
    created = create_run(db_session, "test-workflow", "unpinned")

    run = execute_run(
        db_session,
        created.id,
        workflow=_workflow(_step("first", "alpha"), _step("second", "beta", ["first"])),
    )

    assert run.state == JobState.FAILED
    assert run.error == "step exploded"
    assert reached == [], "a step after a failed one must not run"
    first, second = _steps_of(db_session, run.id)
    assert first.state == JobState.FAILED
    assert first.error == "step exploded"
    # Still pending, not failed: it was never attempted, and saying otherwise
    # would make a run look worse than it was.
    assert second.state == JobState.PENDING
    assert second.started_at is None


def test_a_skill_without_an_implementation_fails_the_run(db_session: Session) -> None:
    created = create_run(db_session, "test-workflow", "unpinned")
    run = execute_run(db_session, created.id, workflow=_workflow(_step("only", "no-such-skill")))
    assert run.state == JobState.FAILED
    assert "no-such-skill" in (run.error or "")
    assert _steps_of(db_session, run.id)[0].state == JobState.FAILED


def test_a_cyclic_workflow_fails_before_any_step_is_recorded(db_session: Session) -> None:
    created = create_run(db_session, "test-workflow", "unpinned")
    run = execute_run(
        db_session,
        created.id,
        workflow=_workflow(_step("a", "alpha", ["b"]), _step("b", "beta", ["a"])),
    )
    assert run.state == JobState.FAILED
    assert "cycle" in (run.error or "")
    assert _steps_of(db_session, run.id) == [], "no step may claim to have been attempted"
