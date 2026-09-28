"""POST /runs refuses a database behind Alembic's head.

Split out of test_runs_api_create.py for the same reason
test_runs_api_create_choices.py and test_runs_api_create_author.py already
are: one more concern would push that file past the project's line limit.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.queue import InMemoryQueue
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_engine, get_queue
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run

_WORKFLOW_NAME = "post-runs-migration-gate-workflow"
_WORKFLOW_YAML = """\
name: post-runs-migration-gate-workflow
version: 1.0.0
schema_version: v1
description: Test-only workflow for POST /runs' migration gate.
steps: []
"""


@dataclass
class _Fixture:
    client: TestClient
    engine: Engine


def _stamp_behind_head(engine: Engine) -> None:
    """Deliberately not fakes.db.stamp_head: this fixture wants the gap the gate catches."""
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0009')"))


@pytest.fixture
def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Fixture]:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / f"{_WORKFLOW_NAME}.yaml").write_text(_WORKFLOW_YAML)

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    _stamp_behind_head(engine)
    with Session(engine) as session:
        session.add(
            Recording(
                id="rec-behind",
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
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = InMemoryQueue
    app.dependency_overrides[get_engine] = lambda: engine
    yield _Fixture(client=TestClient(app), engine=engine)
    get_settings.cache_clear()


def test_post_runs_503_when_the_database_is_behind_alembic_s_head(fixture: _Fixture) -> None:
    response = fixture.client.post(
        "/runs", json={"workflow_name": _WORKFLOW_NAME, "recording_id": "rec-behind"}
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "migrations_pending"
    assert "0009" in body["detail"]
    assert "docker compose" in body["detail"]

    with Session(fixture.engine) as session:
        assert session.scalars(select(Run)).first() is None
