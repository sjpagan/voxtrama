"""HTTP tests for GET /recordings/{id}/choose-workflow's own header, which says
what is about to be processed once it is known: duration and
speaker count, both absent together until a Transcript exists. Split out of
test_workflow_choose_page_already_run.py for the project's own line limit
(tests/test_architecture_limits.py).
"""

from __future__ import annotations

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
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.transcript import Transcript


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    with Session(engine) as session:
        session.add(
            Recording(
                id="rec-1",
                original_filename="clip.wav",
                stored_path="recordings/clip.wav",
                content_sha256="0" * 64,
                duration_seconds=1.0,
                media_format="wav",
            )
        )
        session.commit()

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        data_dir=tmp_path, hardware_profile="base"
    )
    yield TestClient(app)
    get_settings.cache_clear()


def _insert_transcript(tmp_path: Path, speaker_estimate: int | None) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Transcript(
                recording_id="rec-1",
                language="en",
                model_name="whisper",
                model_revision="1",
                hardware_profile="base",
                speaker_estimate=speaker_estimate,
            )
        )
        session.commit()


def test_a_recording_with_no_transcript_yet_shows_no_duration_line(client: TestClient) -> None:
    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "Transcribed ·" not in body


def test_a_transcribed_recording_shows_its_own_duration_and_speaker_count(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_transcript(tmp_path, speaker_estimate=4)

    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "Transcribed ·" in body
    assert "0:01" in body
    assert "4 speakers" in body
