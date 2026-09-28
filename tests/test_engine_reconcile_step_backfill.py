"""Tests for engine.reconcile_step_backfill.close_orphaned_steps.

A RunStep left `running` by a Run that closed before this fix existed has
no way to be found by reconcile_close.close_run itself: that Run is
already final, so close_run never runs again for it. This is the one-time
catch-up worker.main runs at every startup instead.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.reconcile_step_backfill import close_orphaned_steps


def _cancelled_run_with_orphaned_step(session: Session, run_id: str) -> None:
    session.add(
        Run(
            id=run_id,
            workflow_name="demo",
            workflow_version="1.0.0",
            state=RunState.CANCELLED,
            error="cancelled on request",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            finished_at=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        )
    )
    session.add(
        RunStep(
            run_id=run_id,
            step_id="diarize",
            skill="diarize",
            skill_version="1.0.0",
            state=StepState.RUNNING,
            position=0,
        )
    )
    session.commit()


def test_backfill_fails_a_step_still_running_under_an_already_cancelled_run(
    db_session: Session,
) -> None:
    _cancelled_run_with_orphaned_step(db_session, "run-old-cancel")

    closed = close_orphaned_steps(db_session)

    assert closed == 1
    step = db_session.query(RunStep).filter_by(run_id="run-old-cancel").one()
    assert step.state == StepState.FAILED
    assert step.finished_at == datetime(2026, 1, 1, 0, 5)
    assert step.error == "cancelled on request"


def test_backfill_leaves_a_still_running_run_alone(db_session: Session) -> None:
    """The ordinary case, still in progress: nothing here is a run's to fix yet."""
    db_session.add(
        Run(
            id="run-still-going",
            workflow_name="demo",
            workflow_version="1.0.0",
            state=RunState.RUNNING,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db_session.add(
        RunStep(
            run_id="run-still-going",
            step_id="diarize",
            skill="diarize",
            skill_version="1.0.0",
            state=StepState.RUNNING,
            position=0,
        )
    )
    db_session.commit()

    closed = close_orphaned_steps(db_session)

    assert closed == 0
    step = db_session.query(RunStep).filter_by(run_id="run-still-going").one()
    assert step.state == StepState.RUNNING
