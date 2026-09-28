"""Tests for POST /runs/{id}/cancel: request failures.

Split from test_runs_api_cancel.py, which covers the two ways the route
can succeed, kept apart so neither file grows past the project's size limit.
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
from voxtrama.queue.job import JobId, JobState, Progress


@pytest.fixture
def queue() -> InMemoryQueue:
    return InMemoryQueue()


@pytest.fixture
def client(tmp_path: Path, queue: InMemoryQueue) -> Iterator[TestClient]:
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


@pytest.mark.parametrize("state", [RunState.SUCCEEDED, RunState.FAILED, RunState.INTERRUPTED])
def test_cancel_an_already_concluded_run_is_409_conflict(
    tmp_path: Path, client: TestClient, state: RunState
) -> None:
    _insert_run(tmp_path, "run-done", state, job_id="job-d")

    response = client.post("/runs/run-done/cancel")

    assert response.status_code == 409
    assert response.json()["code"] == "conflict"
    assert response.headers["content-type"] == "application/problem+json"
    assert _run_state(tmp_path, "run-done") == state.value


def test_cancel_a_nonexistent_run_is_404_not_found(client: TestClient) -> None:
    response = client.post("/runs/no-such-run/cancel")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.headers["content-type"] == "application/problem+json"


def test_cancel_is_503_when_the_queue_is_unavailable(
    tmp_path: Path, client: TestClient, queue: InMemoryQueue
) -> None:
    _insert_run(tmp_path, "run-unreachable", RunState.RUNNING, job_id="job-u")
    _register_job(queue, "job-u", JobState.RUNNING)
    queue.available = False

    response = client.post("/runs/run-unreachable/cancel")

    assert response.status_code == 503
    assert response.json()["code"] == "queue_unavailable"
    assert response.headers["content-type"] == "application/problem+json"
    assert _run_state(tmp_path, "run-unreachable") == "running"
