"""Tests for GET /recordings/{id}/audio: unsatisfiable ranges and error paths."""

from __future__ import annotations

import wave
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base


def _write_wav(path: Path, seconds: float = 0.5) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * int(8000 * seconds))


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def _create_recording(tmp_path: Path, client: TestClient) -> tuple[str, Path]:
    """Import a small fixture audio file; return its id and stored path."""
    audio = tmp_path / "source" / "clip.wav"
    audio.parent.mkdir()
    _write_wav(audio)

    response = client.post("/recordings", json={"path": str(audio)})
    body = response.json()
    return body["id"], tmp_path / body["stored_path"]


def test_get_audio_416_when_the_range_is_past_the_end(tmp_path: Path, client: TestClient) -> None:
    recording_id, stored_path = _create_recording(tmp_path, client)
    total = len(stored_path.read_bytes())

    response = client.get(
        f"/recordings/{recording_id}/audio",
        headers={"Range": f"bytes={total}-{total + 10}"},
    )

    assert response.status_code == 416
    assert response.json()["code"] == "range_not_satisfiable"
    assert response.headers["content-range"] == f"bytes */{total}"


def test_get_audio_malformed_range_returns_the_whole_file(
    tmp_path: Path, client: TestClient
) -> None:
    recording_id, stored_path = _create_recording(tmp_path, client)

    response = client.get(f"/recordings/{recording_id}/audio", headers={"Range": "not-a-range"})

    assert response.status_code == 200
    assert response.content == stored_path.read_bytes()


def test_get_audio_404_for_an_unknown_recording(client: TestClient) -> None:
    response = client.get("/recordings/does-not-exist/audio")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_get_audio_declared_error_when_the_file_is_missing_from_disk(
    tmp_path: Path, client: TestClient
) -> None:
    recording_id, stored_path = _create_recording(tmp_path, client)
    stored_path.unlink()

    response = client.get(f"/recordings/{recording_id}/audio")

    assert response.status_code == 500
    assert response.json()["code"] == "internal"
