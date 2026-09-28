"""Tests for POST /recordings."""

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
    # A file, not ":memory:": TestClient dispatches requests on a different
    # thread, and an in-memory database is private to the connection that
    # created it, so the request's session would see no tables at all.
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    # The allowed root is the data directory itself: every path a
    # test below imports must resolve under tmp_path for that reason.
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def test_post_recordings_creates_a_recording(tmp_path: Path, client: TestClient) -> None:
    audio = tmp_path / "source" / "clip.wav"
    audio.parent.mkdir()
    _write_wav(audio)

    response = client.post("/recordings", json={"path": str(audio)})

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "clip.wav"
    assert body["media_format"]
    assert body["duration_seconds"] > 0
    assert len(body["content_sha256"]) == 64


def test_post_recordings_404_when_the_path_does_not_exist(
    tmp_path: Path, client: TestClient
) -> None:
    response = client.post("/recordings", json={"path": str(tmp_path / "missing.wav")})

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_post_recordings_415_on_unsupported_media(tmp_path: Path, client: TestClient) -> None:
    fake = tmp_path / "source" / "notes.wav"
    fake.parent.mkdir()
    fake.write_text("this is a text file, not audio")

    response = client.post("/recordings", json={"path": str(fake)})

    assert response.status_code == 415
    body = response.json()
    assert body["code"] == "unsupported_media"
    assert response.headers["content-type"] == "application/problem+json"


def test_post_recordings_422_on_a_body_that_does_not_match_the_schema(client: TestClient) -> None:
    # Proves the RequestValidationError handler in api/errors.py covers
    # every route, not only the ones that raise ProblemException by hand.
    response = client.post("/recordings", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_failed"
    assert response.headers["content-type"] == "application/problem+json"


def test_post_recordings_422_when_the_path_is_outside_the_data_dir(
    tmp_path_factory: pytest.TempPathFactory, client: TestClient
) -> None:
    outside = tmp_path_factory.mktemp("outside") / "clip.wav"
    _write_wav(outside)

    response = client.post("/recordings", json={"path": str(outside)})

    assert response.status_code == 422
    body = response.json()
    # rule_rejected, not validation_failed: same status, different
    # code, and the code is what the API contract declares stable. The detail still
    # says the root is not allowed, rather than "file not found".
    assert body["code"] == "rule_rejected"
    assert "does not resolve under the data directory" in body["detail"]


def test_post_recordings_422_when_a_symlink_inside_the_root_points_outside(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, client: TestClient
) -> None:
    # The check that matters: a path that *looks* like it is under the
    # allowed root, but resolves outside it once the symlink is followed.
    outside = tmp_path_factory.mktemp("outside") / "clip.wav"
    _write_wav(outside)
    link = tmp_path / "source" / "link.wav"
    link.parent.mkdir()
    link.symlink_to(outside)

    response = client.post("/recordings", json={"path": str(link)})

    assert response.status_code == 422
    assert response.json()["code"] == "rule_rejected"
