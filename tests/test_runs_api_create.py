"""Tests for POST /runs: the second creation route, into the queue."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user, stamp_head
from fakes.queue import InMemoryQueue
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_engine, get_queue
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.queue.job import JobState

_WORKFLOW_NAME = "post-runs-workflow"
_WORKFLOW_YAML = """\
name: post-runs-workflow
version: 1.0.0
schema_version: v1
description: Test-only workflow for POST /runs.
steps: []
"""


@pytest.fixture
def queue() -> InMemoryQueue:
    return InMemoryQueue()


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, queue: InMemoryQueue
) -> Iterator[TestClient]:
    # VOXTRAMA_DATA_DIR, not just the get_settings override: workflow lookup
    # (engine.catalog) reads the process-wide settings directly, not through
    # FastAPI's dependency injection.
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / f"{_WORKFLOW_NAME}.yaml").write_text(_WORKFLOW_YAML)

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    stamp_head(engine)  # POST /runs now refuses a schema behind Alembic's head

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[get_engine] = lambda: engine
    yield TestClient(app)
    get_settings.cache_clear()


def _insert_recording(tmp_path: Path, recording_id: str) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Recording(
                id=recording_id,
                original_filename="clip.wav",
                stored_path="recordings/clip.wav",
                content_sha256="0" * 64,
                duration_seconds=1.0,
                media_format="wav",
            )
        )
        session.commit()


def test_post_runs_202_and_the_job_reaches_the_queue(
    tmp_path: Path, client: TestClient, queue: InMemoryQueue
) -> None:
    _insert_recording(tmp_path, "rec-1")

    response = client.post("/runs", json={"workflow_name": _WORKFLOW_NAME, "recording_id": "rec-1"})

    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "pending"
    assert body["recording_id"] == "rec-1"
    # Checked on the queue double itself, not only inferred from the
    # response: the job was submitted, not just described as one.
    assert len(queue._jobs) == 1


def test_post_runs_404_when_the_recording_does_not_exist(client: TestClient) -> None:
    response = client.post(
        "/runs", json={"workflow_name": _WORKFLOW_NAME, "recording_id": "no-such-recording"}
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.headers["content-type"] == "application/problem+json"


def test_post_runs_422_when_the_workflow_name_does_not_resolve(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_recording(tmp_path, "rec-2")

    response = client.post(
        "/runs", json={"workflow_name": "no-such-workflow", "recording_id": "rec-2"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
    assert response.headers["content-type"] == "application/problem+json"


def test_post_runs_503_when_the_queue_is_unavailable_but_the_run_stays_pending(
    tmp_path: Path, client: TestClient, queue: InMemoryQueue
) -> None:
    _insert_recording(tmp_path, "rec-3")
    queue.available = False

    response = client.post("/runs", json={"workflow_name": _WORKFLOW_NAME, "recording_id": "rec-3"})

    assert response.status_code == 503
    assert response.json()["code"] == "queue_unavailable"
    assert response.headers["content-type"] == "application/problem+json"

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        run = session.scalars(select(Run).where(Run.recording_id == "rec-3")).one()
        assert run.state == JobState.PENDING
