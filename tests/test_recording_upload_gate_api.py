"""The gate lives on the routes too, not only on the page.

A box closed in the markup stops nobody: `curl -F` reaches the same route
without the page ever being rendered, and so does a tab left open while
the machine changed underneath it.
"""

from __future__ import annotations

import io
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


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 4000)
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """A real installation that is not ready: no model, schema never migrated."""
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app, follow_redirects=False)


def test_uploading_a_file_is_refused_when_the_installation_is_not_ready(
    client: TestClient,
) -> None:
    response = client.post("/jobs", files=[("files", ("clip.wav", _wav_bytes(), "audio/wav"))])

    assert response.status_code == 503
    assert response.json()["code"] == "not_ready"


def test_the_refusal_names_the_states_that_are_missing(client: TestClient) -> None:
    """A "not ready" that names no state sends the reader to look in four places."""
    response = client.post("/jobs", files=[("files", ("clip.wav", _wav_bytes(), "audio/wav"))])

    detail = response.json()["detail"]
    assert "models_ready" in detail or "schema" in detail


def test_there_is_no_single_file_upload_any_more(client: TestClient) -> None:
    """The home posts /jobs; the older one-file upload went with the old upload box."""
    response = client.post(
        "/recordings/upload", files=[("files", ("clip.wav", _wav_bytes(), "audio/wav"))]
    )

    assert response.status_code in (404, 405)


def test_there_is_no_address_import_any_more(client: TestClient) -> None:
    """Voxtrama does not download audio from third-party sites."""
    response = client.post("/recordings/from-urls", data={"urls": "https://youtu.be/x"})

    assert response.status_code in (404, 405)


def test_nothing_is_written_when_the_gate_refuses(tmp_path: Path, client: TestClient) -> None:
    """The refusal comes before the import, not after it is half written."""
    client.post("/jobs", files=[("files", ("clip.wav", _wav_bytes(), "audio/wav"))])

    assert list((tmp_path / "recordings").glob("*/clip.wav")) == []
