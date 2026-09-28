"""POST /jobs: the home's new-job form creates a job and opens it."""

from __future__ import annotations

import io
import wave
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.queue import InMemoryQueue
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_queue
from voxtrama.api.routes.job_defaults import job_defaults
from voxtrama.api.routes.recording_upload_gate import require_ready
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.workflow.choices import RunChoices


def _wav(seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buffer.getvalue()


@pytest.fixture
def engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    return engine


@pytest.fixture
def client(tmp_path: Path, engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = InMemoryQueue
    app.dependency_overrides[require_ready] = lambda: None
    yield TestClient(app, follow_redirects=False)
    get_settings.cache_clear()


def _parts() -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("files", ("sync-part1.wav", _wav(1.0), "audio/wav")),
        ("files", ("sync-part2.wav", _wav(0.5), "audio/wav")),
    ]


def test_two_parts_become_one_recording_and_the_job_opens(
    tmp_path: Path, client: TestClient, engine
) -> None:
    default = job_defaults(Settings(data_dir=tmp_path)).cores_per_chunk
    chosen = 1 if default != 1 else 2  # within any machine's own cores
    form = {
        "workflow_name": "meeting-decisions",
        "merge": "true",
        "label": "Weekly product sync",
        "context": "Voxtrama, Whisper",
        "cores_per_chunk": str(chosen),
    }
    response = client.post("/jobs", data=form, files=_parts())

    assert response.status_code == 303, response.text
    with Session(engine) as session:
        run = session.scalars(select(Run)).one()
        recording = session.get(Recording, run.recording_id)
    assert response.headers["location"] == f"/runs/{run.id}/view"
    assert run.label == "Weekly product sync"
    assert run.workflow_name == "meeting-decisions"
    assert recording.duration_seconds == pytest.approx(1.5, abs=0.05)
    choices = RunChoices.model_validate(run.choices or {})
    assert choices.cores_per_chunk == chosen
    assert choices.context == "Voxtrama, Whisper"
    assert choices.parallel_chunks is None  # left at its default: no choice


def test_several_files_without_merging_are_refused(client: TestClient) -> None:
    response = client.post("/jobs", data={"workflow_name": "meeting-decisions"}, files=_parts())

    assert response.status_code == 422


def test_transcription_only_runs_the_transcribe_only_workflow(client: TestClient, engine) -> None:
    form = {"workflow_name": "meeting-decisions", "transcribe_only": "true"}
    files = [("files", ("call.wav", _wav(0.5), "audio/wav"))]
    client.post("/jobs", data=form, files=files)

    with Session(engine) as session:
        run = session.scalars(select(Run)).one()
        recording = session.get(Recording, run.recording_id)
    assert run.workflow_name == "transcribe-only"
    assert run.label == "call"  # named after the file when no name is given
    assert recording.original_filename == "call.wav"  # the name the person gave it


def test_a_job_needs_audio(client: TestClient) -> None:
    empty = [("files", ("", b"", "application/octet-stream"))]
    response = client.post("/jobs", data={"workflow_name": "meeting-decisions"}, files=empty)

    assert response.status_code == 422


def test_tracks_recorded_together_are_mixed_not_joined(client: TestClient, engine) -> None:
    """As long as the longest track, not the sum."""
    form = {"workflow_name": "meeting-decisions", "merge": "true", "parts_mode": "tracks"}

    response = client.post("/jobs", data=form, files=_parts())

    assert response.status_code == 303, response.text
    with Session(engine) as session:
        recording = session.get(Recording, session.scalars(select(Run)).one().recording_id)
    assert recording.duration_seconds == pytest.approx(1.0, abs=0.05)
