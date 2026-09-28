"""GET /'s own `?workflow=` carry, split out of
test_shell_runs_list.py for the project's file-length limit
(tests/test_architecture_limits.py).

pages/workflow_library.html's own "Run workflow" lands here with the
workflow it was chosen for; this covers what api.routes.shell does with
it before it ever reaches a pending Recording's own link.
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
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording

_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def _insert_recording(
    tmp_path: Path, recording_id: str, filename: str, imported_at: datetime
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    with Session(engine) as session:
        session.add(
            Recording(
                id=recording_id,
                original_filename=filename,
                stored_path=f"recordings/{recording_id}/{filename}",
                content_sha256="0" * 64,
                duration_seconds=1.0,
                media_format="wav",
                imported_at=imported_at,
            )
        )
        session.commit()


def test_a_workflow_carried_from_the_library_reaches_a_pending_recordings_own_link(
    tmp_path: Path, client: TestClient
) -> None:
    """ "Run workflow" lands here with `?workflow=`, and this page has to forward it
    into the one link that leads to choosing a recording, never dropping
    it just because home page.html has no card of its own to show it on."""
    _insert_recording(tmp_path, "rec1", "team-meeting.wav", _EPOCH)

    body = client.get("/?workflow=meeting-decisions").text

    assert 'href="/recordings/rec1/choose-workflow?workflow=meeting-decisions"' in body


def test_an_unrecognised_workflow_name_is_not_carried_anywhere(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_recording(tmp_path, "rec1", "team-meeting.wav", _EPOCH)

    body = client.get("/?workflow=no-such-workflow").text

    assert 'href="/recordings/rec1/choose-workflow"' in body
    assert "workflow=no-such-workflow" not in body
