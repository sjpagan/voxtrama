"""GET /runs/{id} publishes a step's superseded_by_run_id.

Split out of test_runs_api_detail.py, which was already at the project's
150-line limit, the same reason test_runs_api_list.py gives for its own
split. engine.superseded.superseded_steps' own module carries the
computation's tests; this file only checks the field reaches the response.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.queue.job import JobState


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    # Same pattern as test_runs_api_detail.py's own fixture.
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def _insert_run_with_one_step(tmp_path: Path) -> None:
    """A Recording, a succeeded Run of it, and its one succeeded RunStep "t"."""
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Recording(
                id="rec-1",
                original_filename="meeting.wav",
                stored_path="recordings/meeting.wav",
                content_sha256="1" * 64,
                duration_seconds=1.0,
                media_format="wav",
            )
        )
        session.add(
            Run(
                id="run-5",
                workflow_name="demo",
                workflow_version="1.0.0",
                state=JobState.SUCCEEDED,
                recording_id="rec-1",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.add(
            RunStep(
                run_id="run-5",
                step_id="t",
                skill="t",
                skill_version="1.0.0",
                state=StepState.SUCCEEDED,
                position=0,
            )
        )
        session.commit()


def test_get_run_step_reports_no_supersession_by_default(
    tmp_path: Path, client: TestClient
) -> None:
    """A step's own field is present and null when nothing supersedes it."""
    _insert_run_with_one_step(tmp_path)

    response = client.get("/runs/run-5")

    assert response.status_code == 200
    step = response.json()["steps"][0]
    assert step["step_id"] == "t"
    assert step["superseded_by_run_id"] is None
