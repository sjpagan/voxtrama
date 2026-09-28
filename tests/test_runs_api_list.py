"""Tests for GET /runs's cursor pagination."""

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
from voxtrama.db.models.run import Run
from voxtrama.queue.job import JobState

_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


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


def _insert_run(tmp_path: Path, run_id: str, created_at: datetime) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="demo",
                workflow_version="1.0.0",
                state=JobState.SUCCEEDED,
                created_at=created_at,
            )
        )
        session.commit()


def test_list_runs_pages_without_repeats_or_gaps_across_an_insert(
    tmp_path: Path, client: TestClient
) -> None:
    # r5..r1, newest first: DESC order renders r5, r4, r3, r2, r1.
    for offset, run_id in enumerate(["r1", "r2", "r3", "r4", "r5"]):
        _insert_run(tmp_path, run_id, _EPOCH + timedelta(days=offset))

    first = client.get("/runs", params={"limit": 2}).json()
    assert [item["id"] for item in first["items"]] == ["r5", "r4"]
    assert first["next_cursor"] is not None

    # A run created between the two requests sorts above r5 (it is newer),
    # so it must not shift or repeat a row already past by the cursor.
    _insert_run(tmp_path, "r6", _EPOCH + timedelta(days=10))

    second = client.get("/runs", params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert [item["id"] for item in second["items"]] == ["r3", "r2"]

    third = client.get("/runs", params={"limit": 2, "cursor": second["next_cursor"]}).json()
    assert [item["id"] for item in third["items"]] == ["r1"]
    assert third["next_cursor"] is None


def test_list_runs_422_on_a_malformed_cursor(client: TestClient) -> None:
    response = client.get("/runs", params={"cursor": "not-a-cursor!!"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_failed"
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize("limit", ["101", "0", "abc"])
def test_list_runs_422_on_an_invalid_limit(client: TestClient, limit: str) -> None:
    # Out of range and non-numeric both fail the same Query(ge=1, le=100)
    # constraint, so both must render through the same handler:
    # a limit is never silently clamped, and a bad type is not a 500.
    response = client.get("/runs", params={"limit": limit})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_failed"
    assert response.headers["content-type"] == "application/problem+json"
