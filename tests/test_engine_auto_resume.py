"""A run cut off by a restart is started again once, reusing what it had done."""

from __future__ import annotations

from datetime import UTC, datetime

from fakes.queue import InMemoryQueue, _JobRecord
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState
from voxtrama.engine.auto_resume import resume_interrupted
from voxtrama.engine.reconcile import reconcile_orphan_runs
from voxtrama.queue.job import JobId, JobState, Progress

WORKFLOW = "meeting-decisions"


def _run(session: Session, state: RunState, job_id: str | None = None, **fields) -> Run:
    run = Run(
        workflow_name=WORKFLOW,
        workflow_version="1.0.0",
        state=state,
        job_id=job_id,
        started_at=datetime.now(UTC),
        **fields,
    )
    session.add(run)
    session.commit()
    return run


def _resumes_of(session: Session, run: Run) -> list[Run]:
    return list(session.scalars(select(Run).where(Run.reused_from_run_id == run.id)))


def test_a_run_whose_worker_went_away_is_resumed_from_it(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run = _run(db_session, RunState.RUNNING, job_id="job-1", choices={"summary_detail": 2})
    queue._jobs[JobId("job-1")] = _JobRecord(state=JobState.FAILED, progress=Progress(0, 0, ""))
    closed: list[Run] = []

    reconcile_orphan_runs(db_session, queue, into=closed)
    resumed = resume_interrupted(db_session, queue, closed)

    assert resumed == 1
    [again] = _resumes_of(db_session, run)
    assert again.workflow_name == WORKFLOW
    assert again.choices["summary_detail"] == 2


def test_a_resume_that_is_interrupted_again_is_left_for_the_person(
    db_session: Session, queue: InMemoryQueue
) -> None:
    first = _run(db_session, RunState.INTERRUPTED)
    second = _run(db_session, RunState.INTERRUPTED, reused_from_run_id=first.id)

    assert resume_interrupted(db_session, queue, [second]) == 0
    assert _resumes_of(db_session, second) == []


def test_a_stopped_run_is_never_resumed(db_session: Session, queue: InMemoryQueue) -> None:
    run = _run(db_session, RunState.CANCELLED)

    assert resume_interrupted(db_session, queue, [run]) == 0


def test_a_workflow_that_no_longer_loads_leaves_the_run_interrupted(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run = _run(db_session, RunState.INTERRUPTED)
    run.workflow_name = "no-such-workflow"
    db_session.commit()

    assert resume_interrupted(db_session, queue, [run]) == 0
