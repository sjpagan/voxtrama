"""Tests for GET /runs/{id}/vitality: what a run page reads to tell a dead
worker from a live one.

Same fixture shape as test_runs_api_cancel.py: a file-backed database (the
route dispatches on a different thread than the fixture) plus the fake
queue from tests/fakes/queue.py, both wired through dependency_overrides.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes.queue import InMemoryQueue, _JobRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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


def test_a_pending_run_is_alive_without_asking_the_queue(
    tmp_path: Path, client: TestClient
) -> None:
    """No job_id registered anywhere on the fake queue: a 404/JobNotFound
    here would mean this route asked, which it must not for a Run that is
    not `running` (its own docstring).
    """
    _insert_run(tmp_path, "run-pending", RunState.PENDING)

    response = client.get("/runs/run-pending/vitality")

    assert response.status_code == 200
    assert response.json() == {"vitality": "alive"}


def test_a_running_run_whose_job_is_running_is_alive(
    tmp_path: Path, client: TestClient, queue: InMemoryQueue
) -> None:
    _insert_run(tmp_path, "run-live", RunState.RUNNING, job_id="job-1")
    queue._jobs[JobId("job-1")] = _JobRecord(state=JobState.RUNNING, progress=Progress(0, 0, ""))

    response = client.get("/runs/run-live/vitality")

    assert response.json() == {"vitality": "alive"}


def test_a_running_run_whose_job_the_queue_no_longer_knows_is_gone(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(tmp_path, "run-dead", RunState.RUNNING, job_id="job-ghost")

    response = client.get("/runs/run-dead/vitality")

    assert response.json() == {"vitality": "gone"}


def test_an_unreachable_queue_is_unknown(
    tmp_path: Path, client: TestClient, queue: InMemoryQueue
) -> None:
    _insert_run(tmp_path, "run-unknown", RunState.RUNNING, job_id="job-1")
    queue.available = False

    response = client.get("/runs/run-unknown/vitality")

    assert response.json() == {"vitality": "unknown"}


def test_a_missing_run_is_404(client: TestClient) -> None:
    response = client.get("/runs/no-such-run/vitality")

    assert response.status_code == 404
