"""Tests for GET /runs/{id}.

Pagination is covered separately, in test_runs_api_list.py: the size limit
splits by subject, not by convenience. A step's superseded_by_run_id
is covered separately too, in test_runs_api_detail_superseded.py,
for the same reason.
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
from voxtrama.manifest.output import output_path, write_run_output
from voxtrama.queue.job import JobState


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    # Same pattern as test_recordings_api.py: a file-backed database, since
    # TestClient dispatches requests on a different thread than the fixture.
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def _insert_run(tmp_path: Path, run_id: str, state: JobState, **overrides) -> None:
    """Write a Run row directly: there is no POST /runs yet to create one through."""
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


def test_get_run_returns_output_with_its_claims(tmp_path: Path, client: TestClient) -> None:
    _insert_run(tmp_path, "run-1", JobState.SUCCEEDED)
    write_run_output(
        get_paths(tmp_path).runs_dir,
        "run-1",
        {
            "summarize": {
                "claims": [{"quote": "it works", "evidence": [0, 12], "needs_review": False}]
            }
        },
    )

    response = client.get("/runs/run-1")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "succeeded"
    claim = body["output"]["summarize"]["claims"][0]
    assert claim == {"quote": "it works", "evidence": [0, 12], "needs_review": False}
    # No manifest was written: the evidence count is None, not zero.
    assert body["evidence"] is None


def test_get_run_reports_a_failed_run_with_200(tmp_path: Path, client: TestClient) -> None:
    _insert_run(
        tmp_path,
        "run-2",
        JobState.FAILED,
        error="the transcriber crashed",
        error_code="internal",
        error_step="transcribe",
    )

    response = client.get("/runs/run-2")

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "failed"
    assert body["error"] == {
        "code": "internal",
        "message": "the transcriber crashed",
        "step": "transcribe",
    }


def test_get_run_404_when_the_run_does_not_exist(client: TestClient) -> None:
    response = client.get("/runs/no-such-run")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.headers["content-type"] == "application/problem+json"


def test_get_run_output_is_null_without_an_output_json(tmp_path: Path, client: TestClient) -> None:
    _insert_run(tmp_path, "run-3", JobState.RUNNING)

    response = client.get("/runs/run-3")

    assert response.status_code == 200
    assert response.json()["output"] is None


def test_get_run_500_when_output_json_is_corrupt(tmp_path: Path, client: TestClient) -> None:
    _insert_run(tmp_path, "run-4", JobState.SUCCEEDED)
    path = output_path(get_paths(tmp_path).runs_dir, "run-4")
    path.parent.mkdir(parents=True)
    path.write_text("not json")

    response = client.get("/runs/run-4")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal"
    assert "Traceback" not in body["detail"]
