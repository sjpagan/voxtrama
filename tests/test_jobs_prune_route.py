"""«Clean up» on the Jobs page, and a replaced job's address."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.jobs import seed_job
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.run_redirect import RunRedirect


@pytest.fixture
def engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    return engine


@pytest.fixture
def client(tmp_path: Path, engine) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app, follow_redirects=False)


def test_the_jobs_page_offers_clean_up(client) -> None:
    body = client.get("/jobs").text

    assert 'action="/jobs/prune"' in body


def test_clean_up_removes_an_old_failed_job_and_says_so(client, engine, tmp_path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        job = seed_job(session, tmp_path, "Retro", ["Hi."], state=RunState.FAILED)
        job.finished_at = datetime(2026, 1, 1, tzinfo=UTC)
        session.merge(job)
        recording = session.get(Recording, job.recording_id)
        recording.imported_at = datetime(2026, 1, 1, tzinfo=UTC)
        session.commit()

    response = client.post("/jobs/prune")

    assert response.headers["location"] == "/jobs?cleaned=2"
    with Session(engine) as session:
        assert session.get(Run, job.id) is None
    assert "Leftovers removed: 2." in client.get("/jobs?cleaned=2").text


def test_nothing_to_clean_up_is_said_too(client) -> None:
    assert "Nothing to clean up." in client.get("/jobs?cleaned=0").text


def test_a_replaced_job_s_view_leads_to_the_job_that_replaced_it(client, engine) -> None:
    with Session(engine) as session:
        session.add(RunRedirect(run_id="old", target_run_id="new"))
        session.commit()

    response = client.get("/runs/old/view")

    assert response.status_code == 307
    assert response.headers["location"] == "/runs/new/view"


def test_an_unknown_job_is_still_not_found(client) -> None:
    assert client.get("/runs/nobody/view").status_code == 404
