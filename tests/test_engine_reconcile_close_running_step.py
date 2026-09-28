"""Tests for engine.reconcile_close.close_run's own step-closing half.

A `running` RunStep used to survive `close_run` untouched: a run closed as
`cancelled` or `interrupted` still showed one of its own steps as
`running`, forever, since nothing here ever wrote to it. `pending` is
covered too, the other way: it must stay exactly what it already is.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.reconcile_close import close_run


def _run_with_steps(session: Session, run_id: str) -> Run:
    run = Run(
        id=run_id,
        workflow_name="demo",
        workflow_version="1.0.0",
        state=RunState.RUNNING,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(run)
    session.add_all(
        [
            RunStep(
                run_id=run_id,
                step_id="transcribe",
                skill="transcribe",
                skill_version="1.0.0",
                state=StepState.SUCCEEDED,
                position=0,
            ),
            RunStep(
                run_id=run_id,
                step_id="diarize",
                skill="diarize",
                skill_version="1.0.0",
                state=StepState.RUNNING,
                position=1,
            ),
            RunStep(
                run_id=run_id,
                step_id="extract_concepts",
                skill="extract_concepts",
                skill_version="1.0.0",
                state=StepState.PENDING,
                position=2,
            ),
        ]
    )
    session.commit()
    return run


def _step(session: Session, run_id: str, step_id: str) -> RunStep:
    return session.query(RunStep).filter_by(run_id=run_id, step_id=step_id).one()


def test_closing_a_cancelled_run_fails_the_step_still_running(
    db_session: Session, tmp_path: Path
) -> None:
    run = _run_with_steps(db_session, "run-cancel-step")

    close_run(db_session, get_paths(tmp_path).runs_dir, run, RunState.CANCELLED)

    diarize = _step(db_session, "run-cancel-step", "diarize")
    assert diarize.state == StepState.FAILED
    assert diarize.finished_at is not None
    assert diarize.error == "cancelled on request"


def test_closing_an_interrupted_run_says_why_the_step_stopped(
    db_session: Session, tmp_path: Path
) -> None:
    run = _run_with_steps(db_session, "run-interrupt-step")

    close_run(db_session, get_paths(tmp_path).runs_dir, run, RunState.INTERRUPTED)

    diarize = _step(db_session, "run-interrupt-step", "diarize")
    assert diarize.state == StepState.FAILED
    assert "no longer running" in diarize.error


def test_closing_a_run_leaves_a_step_never_started_exactly_as_it_was(
    db_session: Session, tmp_path: Path
) -> None:
    """A `pending` step never ran: closing the run must not claim otherwise
    (run_cancel._close_never_started's own reasoning, one level up)."""
    run = _run_with_steps(db_session, "run-cancel-pending")

    close_run(db_session, get_paths(tmp_path).runs_dir, run, RunState.CANCELLED)

    extract = _step(db_session, "run-cancel-pending", "extract_concepts")
    assert extract.state == StepState.PENDING
    assert extract.finished_at is None


def test_closing_a_run_leaves_an_already_succeeded_step_alone(
    db_session: Session, tmp_path: Path
) -> None:
    run = _run_with_steps(db_session, "run-cancel-succeeded")

    close_run(db_session, get_paths(tmp_path).runs_dir, run, RunState.CANCELLED)

    transcribe = _step(db_session, "run-cancel-succeeded", "transcribe")
    assert transcribe.state == StepState.SUCCEEDED
