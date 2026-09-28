"""Tests for GET /runs/{id}/view: the run page's static shell.

Same file-backed database shape as tests/test_web_shell.py's client
fixture, with a User row seeded (db.people.local_user needs exactly one)
and Run/RunStep rows written directly: there is no POST /runs in this
test's path. Split from test_web_run_page_labels.py, which covers the
translated-label and connection-badge contract a code review
added, kept apart so neither file grows past the project's size limit.
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
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base, User
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.db.models.user import ROLE_OWNER


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
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
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)
    engine.dispose()


def _insert_run_with_steps(tmp_path: Path, run_id: str, state: RunState) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="Meeting Decisions",
                workflow_version="1.0.0",
                state=state,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.add(
            RunStep(
                run_id=run_id,
                step_id="transcribe",
                skill="transcribe",
                skill_version="1",
                position=0,
                state=StepState.SUCCEEDED,
            )
        )
        # Never reached: the interrupted-run case.
        session.add(
            RunStep(
                run_id=run_id,
                step_id="summarize",
                skill="summarize",
                skill_version="1",
                position=1,
                state=StepState.PENDING,
            )
        )
        session.commit()


def test_the_run_page_renders_the_interior_section_shell(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run_with_steps(tmp_path, "run-1", RunState.RUNNING)

    response = client.get("/runs/run-1/view")

    assert response.status_code == 200
    body = response.text
    assert '<aside class="vx-sidebar"' in body
    assert 'data-run-id="run-1"' in body
    assert 'data-run-final="false"' in body


def test_the_run_page_shows_a_step_it_never_reached(tmp_path: Path, client: TestClient) -> None:
    _insert_run_with_steps(tmp_path, "run-2", RunState.INTERRUPTED)

    response = client.get("/runs/run-2/view")

    body = response.text
    assert 'data-step-id="summarize" data-step-state="pending"' in body
    assert 'data-run-final="true"' in body


def test_the_run_page_loads_its_own_scripts_and_no_cdn(tmp_path: Path, client: TestClient) -> None:
    _insert_run_with_steps(tmp_path, "run-3", RunState.RUNNING)

    response = client.get("/runs/run-3/view")

    body = response.text
    # Each src carries a `?v=<mtime>` cache-busting suffix now, so
    # these check the prefix rather than an exact match on the old URL.
    assert '<script src="/static/js/run_activity.js?v=' in body
    assert '<script src="/static/js/run_vitality.js?v=' in body
    assert '<script src="/static/js/run_page.js?v=' in body
    assert "http://" not in body and "https://" not in body


def test_the_home_row_links_to_the_run_page(tmp_path: Path, client: TestClient) -> None:
    _insert_run_with_steps(tmp_path, "run-4", RunState.SUCCEEDED)

    response = client.get("/")

    assert 'href="/runs/run-4/view"' in response.text


def test_a_missing_run_is_404(client: TestClient) -> None:
    response = client.get("/runs/no-such-run/view")

    assert response.status_code == 404
