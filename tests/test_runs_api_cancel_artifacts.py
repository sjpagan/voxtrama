"""Tests for POST /runs/{id}/cancel: what it leaves on disk for a `running` Run.

Split from test_runs_api_cancel.py, which checks the database and the
response code, kept apart so neither file grows past the project's size
limit. This is the reproduction the correction was written against: a
`running` Run whose manifest and progress file execute_run already wrote
(both still say `running`) and whose job the queue no longer has any
record of. Without engine.reconcile_close.close_run reused by the route,
those two files stay stale forever: reconcile_orphan_runs only looks at
Runs still in `running`, and this one no longer is by the time anyone else
gets to look.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes.queue import InMemoryQueue
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_queue
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.run import Run, RunState
from voxtrama.engine.progress_file import publish_run_state, read_progress
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path, write_run_manifest


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
    app.dependency_overrides[get_queue] = lambda: InMemoryQueue()
    yield TestClient(app)


def _run_object(run_id: str, job_id: str) -> Run:
    """A `running` Run, unpersisted: what write_run_manifest and publish_run_state read.

    Kept separate from the row committed below: a committed instance's
    attributes expire and need a live session to reload, which
    write_run_manifest calling run.id after that session has closed would
    trip over (the same reason test_runs_api_evidence.py's own `_run`
    helper builds its manifest fixture apart from what it persists).
    """
    return Run(
        id=run_id,
        workflow_name="demo",
        workflow_version="1.0.0",
        state=RunState.RUNNING,
        job_id=job_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _seed_running_run_with_artifacts(tmp_path: Path, run_id: str, job_id: str) -> None:
    """A `running` Run as execute_run would have left it: row, manifest, progress file.

    Not going through POST /runs and a real worker: this only needs what
    the route reads and what close_run is supposed to rewrite.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(_run_object(run_id, job_id))
        session.commit()
    runs_dir = get_paths(tmp_path).runs_dir
    write_run_manifest(runs_dir, _run_object(run_id, job_id), [], None, {}, None, None)
    publish_run_state(runs_dir, _run_object(run_id, job_id), message="working")


def test_cancel_of_a_running_run_with_a_vanished_job_rewrites_manifest_and_progress(
    tmp_path: Path, client: TestClient
) -> None:
    _seed_running_run_with_artifacts(tmp_path, "run-ghost-artifacts", "job-ghost-2")
    # job-ghost-2 is never registered on the queue double: cancel() raises
    # JobNotFound, the same as RQBackend does for an id Redis has evicted.

    response = client.post("/runs/run-ghost-artifacts/cancel")

    assert response.status_code == 202
    runs_dir = get_paths(tmp_path).runs_dir
    manifest = Manifest.model_validate_json(
        manifest_path(runs_dir, "run-ghost-artifacts").read_text()
    )
    assert manifest.run.final is True
    assert manifest.failure is not None
    assert manifest.failure.code == "cancelled"
    state = read_progress(runs_dir, "run-ghost-artifacts")
    assert state is not None
    assert state.state == "cancelled"
