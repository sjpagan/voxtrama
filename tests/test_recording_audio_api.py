"""Tests for GET /recordings/{id}/audio: the full file and Range slices."""

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
    # Same pattern as test_recordings_api.py: a file-backed database, since
    # TestClient dispatches requests on a different thread than the fixture.
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


def _create_recording(tmp_path: Path, client: TestClient) -> tuple[str, bytes]:
    """Import a small fixture audio file; return its id and raw bytes."""
    audio = tmp_path / "source" / "clip.wav"
    audio.parent.mkdir()
    _write_wav(audio)

    response = client.post("/recordings", json={"path": str(audio)})
    body = response.json()
    return body["id"], (tmp_path / body["stored_path"]).read_bytes()


def test_get_audio_without_range_returns_the_whole_file(tmp_path: Path, client: TestClient) -> None:
    recording_id, raw_bytes = _create_recording(tmp_path, client)

    response = client.get(f"/recordings/{recording_id}/audio")

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.content == raw_bytes


def test_get_audio_with_range_returns_exactly_the_first_ten_bytes(
    tmp_path: Path, client: TestClient
) -> None:
    recording_id, raw_bytes = _create_recording(tmp_path, client)

    response = client.get(f"/recordings/{recording_id}/audio", headers={"Range": "bytes=0-9"})

    assert response.status_code == 206
    assert response.content == raw_bytes[:10]


def test_get_audio_with_open_ended_range_returns_to_the_end(
    tmp_path: Path, client: TestClient
) -> None:
    recording_id, raw_bytes = _create_recording(tmp_path, client)

    response = client.get(f"/recordings/{recording_id}/audio", headers={"Range": "bytes=5-"})

    assert response.status_code == 206
    assert response.content == raw_bytes[5:]


def test_get_audio_with_suffix_range_returns_the_last_bytes(
    tmp_path: Path, client: TestClient
) -> None:
    recording_id, raw_bytes = _create_recording(tmp_path, client)

    response = client.get(f"/recordings/{recording_id}/audio", headers={"Range": "bytes=-5"})

    assert response.status_code == 206
    assert response.content == raw_bytes[-5:]


def test_get_audio_content_range_states_the_interval_and_total(
    tmp_path: Path, client: TestClient
) -> None:
    recording_id, raw_bytes = _create_recording(tmp_path, client)

    response = client.get(f"/recordings/{recording_id}/audio", headers={"Range": "bytes=0-9"})

    assert response.headers["content-range"] == f"bytes 0-9/{len(raw_bytes)}"
    assert response.headers["content-length"] == "10"


def test_get_audio_declares_the_audio_media_type(tmp_path: Path, client: TestClient) -> None:
    # The <audio> element was told application/octet-stream for a WAV.
    recording_id, _ = _create_recording(tmp_path, client)

    response = client.get(f"/recordings/{recording_id}/audio")

    assert response.headers["content-type"] in ("audio/wav", "audio/x-wav")


def test_a_wav_named_html_is_still_served_as_audio(tmp_path: Path, client: TestClient) -> None:
    """For security: the type came from the uploaded name, and ran as a page."""
    audio = tmp_path / "source" / "clip.html"
    audio.parent.mkdir()
    _write_wav(audio)
    recording_id = client.post("/recordings", json={"path": str(audio)}).json()["id"]

    response = client.get(f"/recordings/{recording_id}/audio")

    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "sandbox"
