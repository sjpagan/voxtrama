"""Tests for DELETE /runs/{id}: request failures.

Split from test_runs_api_delete.py, which covers the ways the route can
succeed, kept apart so neither file grows past the project's size limit.
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
from voxtrama.db.models.run import Run, RunState


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


def test_delete_a_nonexistent_run_is_404_not_found(client: TestClient) -> None:
    response = client.delete("/runs/no-such-run")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.headers["content-type"] == "application/problem+json"


def test_artifacts_of_a_nonexistent_run_is_404_not_found(client: TestClient) -> None:
    response = client.get("/runs/no-such-run/artifacts")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


@pytest.mark.parametrize("state", [RunState.PENDING, RunState.RUNNING])
def test_delete_a_run_still_in_progress_is_409_conflict(
    tmp_path: Path, client: TestClient, state: RunState
) -> None:
    """A run still going is stopped, not deleted: POST .../cancel first."""
    _insert_run(tmp_path, "run-in-progress", state)

    response = client.delete("/runs/run-in-progress")

    assert response.status_code == 409
    assert response.json()["code"] == "conflict"
    assert response.headers["content-type"] == "application/problem+json"

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        assert session.get(Run, "run-in-progress") is not None


def test_a_run_id_crafted_to_escape_runs_dir_deletes_nothing_outside_it(
    tmp_path: Path, client: TestClient
) -> None:
    """`Run.id` is a plain `String` column (the HTTP error taxonomy has no
    rule against it), so nothing stops a row, however it got there, from
    holding something other than a `uuid.uuid4()` value. A bare `..` is
    the one such value an HTTP request can still deliver as `run_id`
    (a literal `/` never reaches the route at all: FastAPI's own routing
    splits the path on it first, so `%2F` either lands on a different
    route or a 404 before this code ever runs. Verified against this
    project's own FastAPI/Starlette version while writing this test).
    Percent-encoded (`%2e%2e`) so TestClient's own URL normalisation does
    not collapse it before the request is even sent, the way it does a
    literal `..` in the path.
    """
    _insert_run(tmp_path, "..", RunState.SUCCEEDED)
    # `runs_dir / ".."` resolves to tmp_path itself: everything in it
    # other than the `runs/` directory this route is allowed to touch.
    outside = tmp_path / "recordings"
    outside.mkdir()
    (outside / "marker.wav").write_text("do not delete me")

    response = client.delete("/runs/%2e%2e")

    assert response.status_code == 204
    assert (outside / "marker.wav").is_file()


def test_artifacts_of_a_run_id_crafted_to_escape_runs_dir_reports_nothing(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(tmp_path, "..", RunState.SUCCEEDED)
    outside = tmp_path / "recordings"
    outside.mkdir()
    (outside / "marker.wav").write_text("do not delete me either")

    response = client.get("/runs/%2e%2e/artifacts")

    assert response.status_code == 200
    assert response.json() == {"file_count": 0, "includes_extracted_text": False}
    assert (outside / "marker.wav").is_file()


def test_delete_leaves_the_runs_directory_itself_alone_when_absent(
    tmp_path: Path, client: TestClient
) -> None:
    """A run cancelled before execute_run wrote nothing under runs_dir at
    all (run_cancel's own `_close_never_started`). Deleting it must not
    fail just because there is no directory to remove.
    """
    _insert_run(tmp_path, "run-nothing-on-disk", RunState.CANCELLED)
    assert not (get_paths(tmp_path).runs_dir / "run-nothing-on-disk").exists()

    response = client.delete("/runs/run-nothing-on-disk")

    assert response.status_code == 204
