"""GET /'s Runs list: ordering, the limit, and the empty state.

test_shell_route.py covers the plumbing (the shell renders, no external
URL leaks); this covers what shows up inside {% block content %} once
there is (or is not) a run to read.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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
from voxtrama.db.models.run import Run, RunState

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


def _insert_run(tmp_path: Path, run_id: str, workflow_name: str, created_at: datetime) -> None:
    # The table shows workflow_name, not id (the page has nowhere for a
    # run's own id to link yet), so each row needs
    # a distinct workflow_name to be told apart by its rendered text.
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name=workflow_name,
                workflow_version="1.0.0",
                state=RunState.SUCCEEDED,
                created_at=created_at,
            )
        )
        session.commit()


def test_root_lists_runs_newest_first(tmp_path: Path, client: TestClient) -> None:
    for offset, run_id in enumerate(["r1", "r2", "r3"]):
        _insert_run(tmp_path, run_id, f"wf-{run_id}", _EPOCH + timedelta(days=offset))

    body = client.get("/").text

    # Reading order in the rendered table follows the newest-first query,
    # not insertion order: wf-r3 (newest) must come before wf-r1 (oldest).
    assert body.index("wf-r3") < body.index("wf-r2") < body.index("wf-r1")


def test_root_with_no_runs_explains_how_to_make_one(client: TestClient) -> None:
    body = client.get("/").text

    # The first job starts from the form right above, not a terminal.
    assert "No jobs yet. The first one starts from the form above." in body


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


def test_a_recording_with_no_run_yet_shows_up_as_not_started(
    tmp_path: Path, client: TestClient
) -> None:
    """The Recent runs table folds in what components/recordings_list.html
    used to render as a second, stateless list.
    """
    _insert_recording(tmp_path, "rec1", "team-meeting.wav", _EPOCH)

    body = client.get("/").text

    assert "team-meeting.wav" in body
    assert 'href="/recordings/rec1/choose-workflow"' in body


def test_a_recording_that_already_has_a_run_does_not_show_up_twice(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_recording(tmp_path, "rec1", "team-meeting.wav", _EPOCH)
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id="r1",
                recording_id="rec1",
                workflow_name="demo",
                workflow_version="1.0.0",
                state=RunState.SUCCEEDED,
                created_at=_EPOCH + timedelta(days=1),
            )
        )
        session.commit()

    body = client.get("/").text

    assert body.count("team-meeting.wav") == 1
    assert 'href="/recordings/rec1/choose-workflow"' not in body
