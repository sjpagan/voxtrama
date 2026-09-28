"""Tests for GET /runs/{id}/view's memory-flavoured failure cases.

Split from test_web_run_page_failure.py, which covers the banner in
general, kept apart so neither file grows past the project's size limit.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base, User
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.user import ROLE_OWNER
from voxtrama.diagnostics.machine import read_machine
from voxtrama.tuning.selector import select_tuning


@contextmanager
def _client(tmp_path: Path, settings: Settings) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(given_name="Owner", family_name="", role=ROLE_OWNER))
        session.commit()

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    engine.dispose()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with _client(tmp_path, Settings(data_dir=tmp_path)) as test_client:
        yield test_client


def _insert_run(tmp_path: Path, run_id: str, state: RunState, error_code: str) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="Meeting Decisions",
                workflow_version="1.0.0",
                state=state,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                error_code=error_code,
                error="boom",
            )
        )
        session.commit()


def test_a_memory_failure_names_used_and_recommended_configuration(tmp_path: Path) -> None:
    """The banner names the run's own chunking configuration.
    The recommendation is read off this machine's own tuning file, not
    hardcoded, since which file applies depends on where this test runs.
    """
    settings = Settings(data_dir=tmp_path, cores_per_chunk=99, parallel_chunks=97)
    tuning = select_tuning(read_machine(tmp_path))
    with _client(tmp_path, settings) as client:
        _insert_run(tmp_path, "run-8", RunState.FAILED, "memory_exhausted")

        body = client.get("/runs/run-8/view").text

    assert 'id="vx-run-failure"' in body
    assert f"97 (recommended {tuning.chunking.parallel_chunks})" in body
    assert f"99 (recommended {tuning.chunking.cores_per_chunk})" in body


def test_an_interrupted_run_is_also_shown_as_a_memory_symptom(
    tmp_path: Path, client: TestClient
) -> None:
    """A worker that vanished mid-step is folded into the same
    banner as an explicit memory failure (rendering.run_failure's own
    docstring says why this cannot be asserted with certainty)."""
    _insert_run(tmp_path, "run-9", RunState.INTERRUPTED, "interrupted")

    body = client.get("/runs/run-9/view").text

    assert 'id="vx-run-failure"' in body


def test_a_cancelled_run_shows_no_failure_banner(tmp_path: Path, client: TestClient) -> None:
    """A person's own choice, not a failure (see rendering.run_failure's own docstring)."""
    _insert_run(tmp_path, "run-10", RunState.CANCELLED, "cancelled")

    body = client.get("/runs/run-10/view").text

    assert 'id="vx-run-failure"' not in body
