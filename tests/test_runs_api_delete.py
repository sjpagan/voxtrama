"""Tests for GET /runs/{id}/artifacts and DELETE /runs/{id}: the ways they succeed.

Request failures (409, 404, and the path-traversal guard) live in
test_runs_api_delete_errors.py. What DELETE leaves behind on the Recording
and Transcript layers lives in test_runs_api_delete_preserves.py. They are kept
apart so no file here grows past the project's size limit.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_settings
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models import Base
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState


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
        session.add(
            RunStep(
                run_id=run_id,
                step_id="transcribe",
                skill="transcribe",
                skill_version="1.0.0",
                state=StepState.SUCCEEDED,
                position=0,
            )
        )
        session.commit()


def _write_run_files(tmp_path: Path, run_id: str, names: list[str]) -> Path:
    run_dir = get_paths(tmp_path).runs_dir / run_id
    run_dir.mkdir(parents=True)
    for name in names:
        (run_dir / name).write_text("{}")
    return run_dir


def test_artifacts_reports_what_is_actually_on_disk(tmp_path: Path, client: TestClient) -> None:
    _insert_run(tmp_path, "run-with-output", RunState.SUCCEEDED)
    _write_run_files(
        tmp_path,
        "run-with-output",
        ["manifest.json", "output.json", "run.log", "progress.json", "workflow.json"],
    )

    response = client.get("/runs/run-with-output/artifacts")

    assert response.status_code == 200
    assert response.json() == {"file_count": 5, "includes_extracted_text": True}


def test_artifacts_of_a_run_that_never_wrote_anything_is_zero(
    tmp_path: Path, client: TestClient
) -> None:
    """A run cancelled before execute_run ever ran (run_cancel's own
    `_close_never_started`) has no directory at all.
    """
    _insert_run(tmp_path, "run-never-started", RunState.CANCELLED)

    response = client.get("/runs/run-never-started/artifacts")

    assert response.status_code == 200
    assert response.json() == {"file_count": 0, "includes_extracted_text": False}


def test_delete_removes_the_row_the_steps_and_the_directory(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(tmp_path, "run-to-delete", RunState.SUCCEEDED)
    run_dir = _write_run_files(tmp_path, "run-to-delete", ["manifest.json", "output.json"])

    response = client.delete("/runs/run-to-delete")

    assert response.status_code == 204
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        assert session.get(Run, "run-to-delete") is None
        assert session.scalars(select(RunStep).where(RunStep.run_id == "run-to-delete")).all() == []
    assert not run_dir.exists()


@pytest.mark.parametrize(
    "state", [RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED, RunState.INTERRUPTED]
)
def test_delete_accepts_every_final_state(
    tmp_path: Path, client: TestClient, state: RunState
) -> None:
    _insert_run(tmp_path, "run-final", state)

    response = client.delete("/runs/run-final")

    assert response.status_code == 204
