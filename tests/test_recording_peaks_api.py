"""Tests for GET /recordings/{id}/peaks: the waveform's numbers, and its cache.

The defect these guard against was not a wrong number: it was a canvas
that stayed blank on a real recording, because the browser used to derive
the shape from the audio itself and gave up past a duration ceiling. The
shape now comes from here, so what matters is that it arrives, that it is
the same on the second call, and that a file with no waveform to give
says so instead of failing the page.
"""

from __future__ import annotations

import math
import struct
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
from voxtrama.ingest.peaks import BUCKET_COUNT, PEAKS_FILENAME


def _write_tone(path: Path, seconds: float = 1.0) -> None:
    """A wav loud in its first half and silent in its second.

    Two halves rather than a constant tone: it is what lets a test tell a
    waveform apart from a flat line of the right length.
    """
    frames = []
    total = int(8000 * seconds)
    for index in range(total):
        loud = index < total // 2
        value = int(20000 * math.sin(index * 0.3)) if loud else 0
        frames.append(struct.pack("<h", value))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"".join(frames))


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


def _import_recording(tmp_path: Path, client: TestClient) -> tuple[str, Path]:
    """Import the fixture; return its id and where its audio landed."""
    audio = tmp_path / "source" / "clip.wav"
    audio.parent.mkdir(exist_ok=True)
    _write_tone(audio)
    body = client.post("/recordings", json={"path": str(audio)}).json()
    return body["id"], tmp_path / body["stored_path"]


def _recording_id(tmp_path: Path, client: TestClient) -> str:
    return _import_recording(tmp_path, client)[0]


def test_peaks_describe_the_recording_rather_than_a_flat_line(
    tmp_path: Path, client: TestClient
) -> None:
    recording_id = _recording_id(tmp_path, client)

    body = client.get(f"/recordings/{recording_id}/peaks").json()

    assert len(body["peaks"]) == BUCKET_COUNT
    assert all(0.0 <= level <= 1.0 for level in body["peaks"])
    # The fixture is loud then silent: the first half must stand above the
    # second, or the numbers are not describing this audio.
    half = BUCKET_COUNT // 2
    assert max(body["peaks"][:half]) > 0.5
    assert max(body["peaks"][half + 10 :]) < 0.1


def test_the_second_request_is_served_from_the_cache_beside_the_audio(
    tmp_path: Path, client: TestClient
) -> None:
    """The computation lands once, on whoever opens the result first."""
    recording_id = _recording_id(tmp_path, client)
    first = client.get(f"/recordings/{recording_id}/peaks").json()["peaks"]

    caches = list(tmp_path.rglob(PEAKS_FILENAME))
    assert len(caches) == 1
    # Written inside the data directory and nowhere else.
    assert tmp_path in caches[0].parents

    assert client.get(f"/recordings/{recording_id}/peaks").json()["peaks"] == first


def test_a_recording_that_does_not_exist_is_404(client: TestClient) -> None:
    assert client.get("/recordings/no-such-id/peaks").status_code == 404


def test_audio_that_cannot_be_decoded_is_422_not_500(tmp_path: Path, client: TestClient) -> None:
    """The recording exists and the request is fine: it is the media that
    cannot give a waveform, and the player is meant to carry on without one.
    """
    # The stored path the API itself reports, not a guess: the import leaves a
    # `resampled_16k.wav` beside the original, and corrupting that one
    # would leave the real audio readable and the test green for nothing.
    recording_id, stored = _import_recording(tmp_path, client)
    stored.write_bytes(b"not audio at all")

    response = client.get(f"/recordings/{recording_id}/peaks")

    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_media"
