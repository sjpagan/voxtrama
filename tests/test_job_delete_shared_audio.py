"""Deleting a job whose audio another job also uses.

A regenerated job runs on the same recording as the job it came from. Asked
to delete the old one with all three boxes ticked, Voxtrama answered 409
"The audio is used by another job", as raw JSON, and deleted nothing.

Each job behaves as if the audio were its own. Deleting a job, or only
its audio, never fails because another job shares the recording: this job
lets go of it, the other keeps it, and the files go with the last job
that uses them.
"""

from __future__ import annotations

from collections.abc import Iterator
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

ALL_THREE = {"audio": "true", "transcript": "true", "recap": "true"}


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


def _two_jobs_on_one_recording(engine, tmp_path: Path, **second) -> tuple[Run, Run]:
    with Session(engine, expire_on_commit=False) as session:
        first = seed_job(session, tmp_path, "AiGen Full", ["We ship on Friday."])
        other = Run(
            workflow_name="transcribe-only",
            workflow_version="1",
            recording_id=first.recording_id,
            state=second.get("state", RunState.SUCCEEDED),
            reused_from_run_id=second.get("reused_from"),
        )
        session.add(other)
        session.commit()
        return first, other


def _audio(tmp_path: Path, run: Run) -> Path:
    return tmp_path / "recordings" / run.recording_id / "audio.wav"


def test_the_whole_job_goes_and_the_other_keeps_the_audio(client, engine, tmp_path) -> None:
    first, other = _two_jobs_on_one_recording(engine, tmp_path)

    response = client.post(f"/jobs/{first.id}/delete", data=ALL_THREE)

    assert response.status_code == 303
    with Session(engine) as session:
        assert session.get(Run, first.id) is None
        assert session.get(Recording, other.recording_id) is not None
    assert _audio(tmp_path, first).exists()


def test_only_the_audio_lets_go_of_it_without_touching_the_other(client, engine, tmp_path) -> None:
    first, other = _two_jobs_on_one_recording(engine, tmp_path)

    response = client.post(f"/jobs/{first.id}/delete", data={"audio": "true"})

    assert response.status_code == 303
    with Session(engine) as session:
        assert session.get(Run, first.id).recording_id is None
        assert session.get(Run, other.id).recording_id == first.recording_id
    assert _audio(tmp_path, first).exists()
    assert "vx-run-player" not in client.get(f"/runs/{first.id}/view").text


def test_the_last_job_to_go_takes_the_audio_with_it(client, engine, tmp_path) -> None:
    first, other = _two_jobs_on_one_recording(engine, tmp_path)
    client.post(f"/jobs/{first.id}/delete", data=ALL_THREE)

    client.post(f"/jobs/{other.id}/delete", data=ALL_THREE)

    assert not _audio(tmp_path, first).exists()


def test_a_job_whose_regeneration_is_running_waits(client, engine, tmp_path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        first = seed_job(session, tmp_path, "AiGen Full", ["We ship on Friday."])
    _two_jobs_on_one_recording(engine, tmp_path, state=RunState.RUNNING, reused_from=first.id)

    response = client.post(f"/jobs/{first.id}/delete", data=ALL_THREE)

    assert response.status_code == 409
    assert "still running" in response.json()["title"]
