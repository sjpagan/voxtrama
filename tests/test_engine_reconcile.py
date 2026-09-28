"""Tests for engine.reconcile.reconcile_orphan_runs: which runs it closes.

Split from test_engine_reconcile_manifest.py, which covers what closing a
run writes to disk. Kept apart so neither file grows past the
project's size limit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fakes.queue import InMemoryQueue, _JobRecord
from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState
from voxtrama.engine.reconcile import reconcile_orphan_runs
from voxtrama.queue.job import JobId, JobState, Progress


def _running_run(
    session: Session, *, job_id: str | None, workflow_name: str = "no-such-workflow"
) -> Run:
    run = Run(
        workflow_name=workflow_name,
        workflow_version="1.0.0",
        state=RunState.RUNNING,
        job_id=job_id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    session.commit()
    return run


def _set_job_state(queue: InMemoryQueue, job_id: str, state: JobState) -> None:
    queue._jobs[JobId(job_id)] = _JobRecord(state=state, progress=Progress(0, 0, ""))


def test_a_run_whose_job_failed_becomes_interrupted_with_a_readable_error(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run = _running_run(db_session, job_id="job-1")
    _set_job_state(queue, "job-1", JobState.FAILED)

    closed = reconcile_orphan_runs(db_session, queue)

    assert closed == 1
    db_session.refresh(run)
    assert run.state == RunState.INTERRUPTED
    assert run.error_code == "interrupted"
    assert run.error and "no longer running" in run.error


def test_a_run_whose_job_is_still_running_is_left_alone(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run = _running_run(db_session, job_id="job-2")
    _set_job_state(queue, "job-2", JobState.RUNNING)

    closed = reconcile_orphan_runs(db_session, queue)

    assert closed == 0
    db_session.refresh(run)
    assert run.state == RunState.RUNNING


def test_a_run_with_no_job_id_is_orphaned(db_session: Session, queue: InMemoryQueue) -> None:
    run = _running_run(db_session, job_id=None)

    closed = reconcile_orphan_runs(db_session, queue)

    assert closed == 1
    db_session.refresh(run)
    assert run.state == RunState.INTERRUPTED


def test_a_run_whose_job_the_queue_has_never_heard_of_is_orphaned(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run = _running_run(db_session, job_id="ghost-job")
    # Deliberately never registered on the fake queue: queue.status raises
    # JobNotFound, the same as RQBackend does for an id Redis has evicted.

    closed = reconcile_orphan_runs(db_session, queue)

    assert closed == 1
    db_session.refresh(run)
    assert run.state == RunState.INTERRUPTED


def test_an_unreachable_queue_touches_no_run_at_all(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run = _running_run(db_session, job_id="job-5")
    _set_job_state(queue, "job-5", JobState.FAILED)
    queue.available = False

    closed = reconcile_orphan_runs(db_session, queue)

    assert closed == 0
    db_session.refresh(run)
    assert run.state == RunState.RUNNING


def test_a_run_whose_job_was_cancelled_becomes_cancelled_not_interrupted(
    db_session: Session, queue: InMemoryQueue
) -> None:
    """The defect this closes: a cancelled job used to read as `interrupted`."""
    run = _running_run(db_session, job_id="job-7")
    _set_job_state(queue, "job-7", JobState.CANCELLED)

    closed = reconcile_orphan_runs(db_session, queue)

    assert closed == 1
    db_session.refresh(run)
    assert run.state == RunState.CANCELLED
    assert run.error_code == "cancelled"
    assert run.error == "cancelled on request"


def test_runs_already_settled_are_never_reconsidered(
    db_session: Session, queue: InMemoryQueue
) -> None:
    succeeded = _running_run(db_session, job_id="job-6a")
    succeeded.state = RunState.SUCCEEDED
    failed = _running_run(db_session, job_id="job-6b")
    failed.state = RunState.FAILED
    db_session.commit()

    closed = reconcile_orphan_runs(db_session, queue)

    assert closed == 0
    db_session.refresh(succeeded)
    db_session.refresh(failed)
    assert succeeded.state == RunState.SUCCEEDED
    assert failed.state == RunState.FAILED
