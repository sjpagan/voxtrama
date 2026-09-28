"""Tests for POST /runs/{id}/cancel: the ways it can succeed.

Request failures (409, 404, 503) live in test_runs_api_cancel_errors.py,
kept apart so neither file grows past the project's size limit.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes.queue import InMemoryQueue, _JobRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_queue
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.run import Run, RunState
from voxtrama.engine.reconcile import reconcile_orphan_runs
from voxtrama.queue.job import JobId, JobState, Progress


@pytest.fixture
def queue() -> InMemoryQueue:
    return InMemoryQueue()


@pytest.fixture
def client(tmp_path: Path, queue: InMemoryQueue) -> Iterator[TestClient]:
    # File-backed database, not :memory:: TestClient dispatches requests on
    # a different thread than the fixture (same pattern as the other
    # tests/test_runs_api_*.py files).
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = lambda: queue
    yield TestClient(app)


def _insert_run(tmp_path: Path, run_id: str, state: RunState, **overrides) -> None:
    """Write a Run row directly: there is no POST /runs in this test's path."""
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="demo",
                workflow_version="1.0.0",
                state=state,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                **overrides,
            )
        )
        session.commit()


def _run_state(tmp_path: Path, run_id: str) -> str:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        return session.scalars(select(Run.state).where(Run.id == run_id)).one()


def _register_job(queue: InMemoryQueue, job_id: str, state: JobState) -> None:
    queue._jobs[JobId(job_id)] = _JobRecord(state=state, progress=Progress(0, 0, ""))


def test_cancel_pending_run_is_202_and_already_cancelled(
    tmp_path: Path, client: TestClient, queue: InMemoryQueue
) -> None:
    _insert_run(tmp_path, "run-pending", RunState.PENDING, job_id="job-p")
    _register_job(queue, "job-p", JobState.PENDING)

    response = client.post("/runs/run-pending/cancel")

    assert response.status_code == 202
    assert response.json()["state"] == "cancelled"
    assert _run_state(tmp_path, "run-pending") == "cancelled"
    assert queue.status(JobId("job-p")) == JobState.CANCELLED


def test_cancel_running_run_is_202_and_cancelled_at_once(
    tmp_path: Path, client: TestClient, queue: InMemoryQueue
) -> None:
    _insert_run(tmp_path, "run-running", RunState.RUNNING, job_id="job-r")
    _register_job(queue, "job-r", JobState.RUNNING)

    response = client.post("/runs/run-running/cancel")

    assert response.status_code == 202
    # «Stop job» used to leave the page on «running» until the worker
    # restarted. The queue kills the job now, so the Run closes here.
    assert response.json()["state"] == "cancelled"
    assert _run_state(tmp_path, "run-running") == "cancelled"
    assert queue.status(JobId("job-r")) == JobState.CANCELLED


def test_cancel_a_running_run_whose_job_the_queue_no_longer_knows_is_202_and_cancelled(
    tmp_path: Path, client: TestClient, queue: InMemoryQueue
) -> None:
    """RQ discards a job some time after it
    concludes (its own TTL), so a `running` Run whose job is gone by the
    time someone cancels it is the ordinary case under load, not a fault.
    It must read as `not found on the queue` = `nothing to kill`, the
    same as a null job_id, not surface as an unhandled 500.
    """
    _insert_run(tmp_path, "run-ghost-job", RunState.RUNNING, job_id="job-ghost")
    # Deliberately never registered on the fake queue: queue.cancel raises
    # JobNotFound, the same as RQBackend does for an id Redis has evicted.

    response = client.post("/runs/run-ghost-job/cancel")

    assert response.status_code == 202
    assert response.json()["state"] == "cancelled"
    assert _run_state(tmp_path, "run-ghost-job") == "cancelled"


def test_reconciling_after_cancel_leaves_the_run_cancelled(
    tmp_path: Path, client: TestClient, queue: InMemoryQueue
) -> None:
    """Reconciliation, seen from the route side: already closed by the cancel, the
    reconciliation at the next worker start has nothing left to change."""
    _insert_run(tmp_path, "run-then-reconciled", RunState.RUNNING, job_id="job-c")
    _register_job(queue, "job-c", JobState.RUNNING)
    client.post("/runs/run-then-reconciled/cancel")

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        closed = reconcile_orphan_runs(session, queue)
        assert closed == 0

    assert _run_state(tmp_path, "run-then-reconciled") == "cancelled"
