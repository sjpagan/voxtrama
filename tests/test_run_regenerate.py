"""POST /runs/{id}/regenerate: «Regenerate job» runs a concluded job
again on the same recording, with the workflow and the job's fields as the
panel posts them, adopting every step whose choices did not change.

Replaces test_run_switch_workflow.py: the old «Change workflow» could only
switch workflow, and «Regenerate job» is what took its place.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.queue import InMemoryQueue
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_queue
from voxtrama.api.routes.recording_upload_gate import require_ready
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState


def _seed(engine: Engine, state: RunState) -> None:
    with Session(engine) as session:
        session.add(
            Recording(
                id="rec-1",
                original_filename="clip.wav",
                stored_path="recordings/clip.wav",
                content_sha256="0" * 64,
                duration_seconds=1.0,
                media_format="wav",
            )
        )
        session.add(
            Run(
                id="run-1",
                recording_id="rec-1",
                workflow_name="meeting-decisions",
                workflow_version="1.0.0",
                state=state,
                label="Weekly sync",
            )
        )
        session.commit()


@pytest.fixture
def queue() -> InMemoryQueue:
    return InMemoryQueue()


def _client(tmp_path: Path, queue: InMemoryQueue, state: RunState) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    _seed(engine, state)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[require_ready] = lambda: None
    return TestClient(app)


def _new_run(tmp_path: Path) -> Run:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        run = session.scalars(select(Run).where(Run.id != "run-1")).one()
        session.expunge(run)
        return run


def test_regenerating_starts_a_new_job_on_the_same_recording(
    tmp_path: Path, queue: InMemoryQueue
) -> None:
    client = _client(tmp_path, queue, RunState.SUCCEEDED)

    response = client.post(
        "/runs/run-1/regenerate",
        data={"workflow_name": "lesson-companion", "summary_detail": "5"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    run = _new_run(tmp_path)
    assert response.headers["location"] == f"/runs/{run.id}/view"
    assert run.recording_id == "rec-1"
    assert run.reused_from_run_id == "run-1"
    assert run.workflow_name == "lesson-companion"
    assert run.label == "Weekly sync"
    assert run.replaces_run_id == "run-1"  # Replaces it once it succeeds
    assert run.choices["summary_detail"] == 5
    assert len(queue._jobs) == 1


def test_a_job_still_running_cannot_be_regenerated(tmp_path: Path, queue: InMemoryQueue) -> None:
    client = _client(tmp_path, queue, RunState.RUNNING)

    response = client.post("/runs/run-1/regenerate", data={"workflow_name": "meeting-decisions"})

    assert response.status_code == 409
    assert not queue._jobs


def test_a_failed_job_can_be_regenerated(tmp_path: Path, queue: InMemoryQueue) -> None:
    """The steps a failed job finished are adopted; the rest run again."""
    client = _client(tmp_path, queue, RunState.FAILED)

    response = client.post(
        "/runs/run-1/regenerate",
        data={"workflow_name": "meeting-decisions"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert _new_run(tmp_path).reused_from_run_id == "run-1"


def test_an_unknown_workflow_is_rejected(tmp_path: Path, queue: InMemoryQueue) -> None:
    client = _client(tmp_path, queue, RunState.SUCCEEDED)

    response = client.post("/runs/run-1/regenerate", data={"workflow_name": "no-such-workflow"})

    assert response.status_code == 422


def test_a_job_that_does_not_exist_is_404(tmp_path: Path, queue: InMemoryQueue) -> None:
    client = _client(tmp_path, queue, RunState.SUCCEEDED)

    response = client.post("/runs/nope/regenerate", data={"workflow_name": "meeting-decisions"})

    assert response.status_code == 404
