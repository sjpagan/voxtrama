"""The Jobs section and its deletion dialog."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.jobs import seed_job
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Transcript


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


def _job(engine, tmp_path: Path, label: str, **kwargs) -> Run:
    with Session(engine, expire_on_commit=False) as session:
        return seed_job(session, tmp_path, label, ["We ship on Friday."], **kwargs)


def test_every_job_is_listed_newest_first_with_its_columns(client, engine, tmp_path) -> None:
    _job(engine, tmp_path, "Older sync", day=1)
    _job(engine, tmp_path, "Newer sync", day=2)

    body = client.get("/jobs").text

    assert body.index("Newer sync") < body.index("Older sync")
    assert "Meeting decisions" in body
    assert "2:05" in body  # audio length
    assert 'href="/"' in body and "New job" in body


def test_each_row_carries_its_created_at_as_a_utc_instant_for_the_browser(
    client, engine, tmp_path
) -> None:
    """The Date column's `<time>`: rendering.jobs.job_rows must mark
    `run.created_at` (naive, but UTC) with its offset, or a browser reading
    it as local time would shift the day instead of fixing it."""
    _job(engine, tmp_path, "Sync", day=2)

    body = client.get("/jobs").text

    assert '<time datetime="2026-09-02T00:00:00+00:00" data-local="date">' in body


def test_delete_opens_the_three_boxes_for_a_finished_job(client, engine, tmp_path) -> None:
    run = _job(engine, tmp_path, "Sync")

    body = client.get(f"/jobs?delete={run.id}").text

    assert f'action="/jobs/{run.id}/delete"' in body
    for box in ("audio", "transcript", "recap"):
        assert f'name="{box}"' in body


def test_a_job_still_running_offers_no_delete(client, engine, tmp_path) -> None:
    run = _job(engine, tmp_path, "Busy", state=RunState.RUNNING)

    body = client.get(f"/jobs?delete={run.id}").text

    assert "Delete selected" not in body


def test_only_what_is_ticked_is_deleted(client, engine, tmp_path) -> None:
    run = _job(engine, tmp_path, "Sync")

    response = client.post(f"/jobs/{run.id}/delete", data={"recap": "true"})

    assert response.status_code == 303
    assert not (tmp_path / "runs" / run.id / "output.json").exists()
    with Session(engine) as session:
        assert session.get(Run, run.id) is not None
        assert session.scalar(select(Transcript)) is not None
    assert (tmp_path / "recordings" / run.recording_id / "audio.wav").exists()


def test_all_three_remove_the_job_itself(client, engine, tmp_path) -> None:
    run = _job(engine, tmp_path, "Sync")
    ticked = {"audio": "true", "transcript": "true", "recap": "true"}

    client.post(f"/jobs/{run.id}/delete", data=ticked)

    with Session(engine) as session:
        assert session.get(Run, run.id) is None
        assert session.get(Recording, run.recording_id) is None
        assert session.scalar(select(Transcript)) is None
    assert not (tmp_path / "recordings" / run.recording_id).exists()
