"""Tests for how GET /runs/{id} reads evidence.

The count comes from manifest.json's own evidence field, never recomputed
by walking output.json: the engine already counted it once.
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
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.run import Run
from voxtrama.manifest.evidence import ClaimCount
from voxtrama.manifest.writer import manifest_path, write_run_manifest
from voxtrama.queue.job import JobState


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


def _run(run_id: str) -> Run:
    """A Run with the fields write_run_manifest and the route both need.

    Not persisted here: DB persistence and the object write_run_manifest
    reads from are two different needs of the same values, kept separate
    so committing one is never required to read the other back (SQLAlchemy
    would expire and re-query a committed instance's attributes, which a
    closed session can no longer do).
    """
    return Run(
        id=run_id,
        workflow_name="demo",
        workflow_version="1.0.0",
        state=JobState.SUCCEEDED,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _insert_run(tmp_path: Path, run_id: str) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(_run(run_id))
        session.commit()


def test_get_run_evidence_comes_from_the_manifest(tmp_path: Path, client: TestClient) -> None:
    _insert_run(tmp_path, "run-1")
    write_run_manifest(
        get_paths(tmp_path).runs_dir,
        _run("run-1"),
        [],
        None,
        {},
        None,
        None,
        evidence={"summarize": ClaimCount(claims=3, needs_review=1)},
    )

    response = client.get("/runs/run-1")

    assert response.json()["evidence"] == {"claims": 3, "needs_review": 1}


def test_get_run_500_when_manifest_json_is_corrupt(tmp_path: Path, client: TestClient) -> None:
    _insert_run(tmp_path, "run-2")
    path = manifest_path(get_paths(tmp_path).runs_dir, "run-2")
    path.parent.mkdir(parents=True)
    path.write_text("not json")

    response = client.get("/runs/run-2")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal"
    assert "Traceback" not in body["detail"]
