"""What a new-job upload may weigh (a security check).

No limit existed, and POST /jobs read every part whole into memory: a
multi-gigabyte file meant that much RAM in the web process.
"""

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
from voxtrama.api.routes import upload_limits
from voxtrama.api.routes.recording_upload_gate import require_ready
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.run import Run


def _wav(seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buffer.getvalue()


def _parts() -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", ("call.wav", _wav(1.0), "audio/wav"))]


@pytest.fixture
def engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
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
    app.dependency_overrides[get_queue] = InMemoryQueue
    app.dependency_overrides[require_ready] = lambda: None
    return TestClient(app, follow_redirects=False)


def test_an_upload_over_the_limit_is_refused_before_it_is_read(
    tmp_path: Path, client: TestClient, engine
) -> None:
    """No limit existed, and every part was read whole into memory."""
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        data_dir=tmp_path, max_upload_mb=1
    )
    big = [("files", ("long.wav", _wav(40.0), "audio/wav"))]  # about 1.2 MB

    response = client.post("/jobs", data={"workflow_name": "meeting-decisions"}, files=big)

    assert response.status_code == 413
    with Session(engine) as session:
        assert session.scalars(select(Run)).first() is None


def test_an_upload_the_data_folder_cannot_hold_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        upload_limits.shutil, "disk_usage", lambda path: type("U", (), {"free": 1000})()
    )

    response = client.post("/jobs", data={"workflow_name": "meeting-decisions"}, files=_parts())

    assert response.status_code == 507
