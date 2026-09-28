"""Tests for GET /runs/{id}/view's translated-label and connection-badge
contract.

Split from test_web_run_page.py, which covers the page's static shell,
kept apart so neither file grows past the project's file size limit. A
code review is why this file exists at all: the first
version wrote `{{ run.state }}` and an English `STEP_LABELS` dictionary
straight into the page, both bypassing the translation catalogue.
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


def _insert_run(tmp_path: Path, run_id: str, state: RunState) -> None:
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
        session.commit()


def test_the_run_state_shown_is_translated_not_the_raw_domain_value(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(tmp_path, "run-label", RunState.RUNNING)

    body = client.get("/runs/run-label/view").text

    assert '<span id="vx-run-state-label">Running</span>' in body


def test_the_run_page_renders_the_label_catalog_for_its_own_javascript(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(tmp_path, "run-catalog", RunState.RUNNING)

    body = client.get("/runs/run-catalog/view").text

    assert '<ul id="vx-state-labels" hidden>' in body
    assert '<li data-catalog="step" data-state="pending">Waiting</li>' in body
    assert '<li data-catalog="run" data-state="cancelled">Cancelled</li>' in body


def test_the_run_page_has_a_hidden_connection_badge_distinct_from_vitality(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(tmp_path, "run-conn", RunState.RUNNING)

    body = client.get("/runs/run-conn/view").text

    assert '<span id="vx-run-connection" class="vx-badge vx-badge--warning" hidden>' in body
    assert '<span id="vx-run-vitality" class="vx-badge vx-badge--warning" hidden>' in body
