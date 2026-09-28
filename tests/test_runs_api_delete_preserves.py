"""Tests for DELETE /runs/{id}: what it never touches.

Split from test_runs_api_delete.py, which covers the row, the steps and
the run's own directory, kept apart so neither file grows past the
project's size limit. The Recording, its audio, and the Transcript a run produced
are a different layer (see api.routes.run_delete's own module docstring)
and this file is where that boundary is checked.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_settings
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Transcript


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def _insert_run(tmp_path: Path, run_id: str, state: RunState, **overrides) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="demo",
                workflow_version="1.0.0",
                state=state,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                **overrides,
            )
        )
        session.commit()


def test_delete_never_touches_the_recording_or_its_audio(
    tmp_path: Path, client: TestClient
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    audio_path = get_paths(tmp_path).recordings_dir / "meeting.wav"
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"not really audio")
    with Session(engine) as session:
        session.add(
            Recording(
                id="rec-1",
                original_filename="meeting.wav",
                stored_path="recordings/meeting.wav",
                content_sha256="a" * 64,
                duration_seconds=1.0,
                media_format="wav",
            )
        )
        session.commit()
    _insert_run(tmp_path, "run-with-recording", RunState.SUCCEEDED, recording_id="rec-1")

    response = client.delete("/runs/run-with-recording")

    assert response.status_code == 204
    assert audio_path.is_file()
    with Session(engine) as session:
        assert session.get(Recording, "rec-1") is not None


def test_delete_of_a_run_that_produced_no_transcript_leaves_nothing_behind_to_check(
    tmp_path: Path, client: TestClient
) -> None:
    """No Transcript.produced_by_run_id points at this run: nothing to decide."""
    _insert_run(tmp_path, "run-no-transcript", RunState.FAILED)

    response = client.delete("/runs/run-no-transcript")

    assert response.status_code == 204


def test_delete_keeps_the_transcript_this_run_produced(tmp_path: Path, client: TestClient) -> None:
    """The safe default: a Transcript this run produced is never deleted
    here, because telling "reused by another run" apart from "not reused"
    with certainty needs more than a `produced_by_run_id` lookup. See
    run_delete.py's own module docstring for why.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Recording(
                id="rec-2",
                original_filename="call.wav",
                stored_path="recordings/call.wav",
                content_sha256="b" * 64,
                duration_seconds=1.0,
                media_format="wav",
            )
        )
        session.add(
            Transcript(
                id="transcript-1",
                recording_id="rec-2",
                language="en",
                model_name="whisper-fake",
                model_revision="rev-1",
                hardware_profile="low",
                produced_by_run_id="run-with-transcript",
                produced_by_step_id="transcribe",
            )
        )
        session.commit()
    _insert_run(tmp_path, "run-with-transcript", RunState.SUCCEEDED, recording_id="rec-2")

    response = client.delete("/runs/run-with-transcript")

    assert response.status_code == 204
    with Session(engine) as session:
        assert session.get(Transcript, "transcript-1") is not None
