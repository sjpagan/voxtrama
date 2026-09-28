"""POST /runs: the Run it creates carries created_by.

Split out of test_runs_api_create.py, which pushed past the project's
150-line file limit the moment this test was added. Same split, and
for the same reason, as test_runs_api_create_choices.py before it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user, stamp_head
from fakes.queue import InMemoryQueue
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_engine, get_queue
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.people import local_user

_WORKFLOW_NAME = "post-runs-author-workflow"
_WORKFLOW_YAML = """\
name: post-runs-author-workflow
version: 1.0.0
schema_version: v1
description: Test-only workflow for POST /runs' created_by.
steps: []
"""


@pytest.fixture
def queue() -> InMemoryQueue:
    return InMemoryQueue()


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, queue: InMemoryQueue
) -> Iterator[TestClient]:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / f"{_WORKFLOW_NAME}.yaml").write_text(_WORKFLOW_YAML)

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    stamp_head(engine)  # POST /runs now refuses a schema behind Alembic's head

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[get_engine] = lambda: engine
    yield TestClient(app)
    get_settings.cache_clear()


def _insert_recording(tmp_path: Path, recording_id: str) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Recording(
                id=recording_id,
                original_filename="clip.wav",
                stored_path="recordings/clip.wav",
                content_sha256="0" * 64,
                duration_seconds=1.0,
                media_format="wav",
            )
        )
        session.commit()


def test_post_runs_run_row_carries_the_local_user_as_created_by(
    tmp_path: Path, client: TestClient
) -> None:
    """The created_by half of run authorship: the route fills the Run's
    created_by with the Community Edition's one local user,
    rather than leaving it NULL the way a row written before migration
    0011 would read.
    """
    _insert_recording(tmp_path, "rec-1")

    response = client.post("/runs", json={"workflow_name": _WORKFLOW_NAME, "recording_id": "rec-1"})
    run_id = response.json()["id"]

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run.created_by == local_user(session).id
