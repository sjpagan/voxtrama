"""Tests for the run page's step markers and its own name.

Split from test_web_run_page_chain.py, which covers the chain's per-step
state and its step count, kept apart so neither file grows past the
project's 150-line file limit.
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
from voxtrama.db.models.recording import Recording
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


def _insert_run_with_a_named_recording(tmp_path: Path, run_id: str) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Recording(
                id="rec-1",
                original_filename="Team retro, 24 Sep.m4a",
                stored_path="recordings/team-retro.m4a",
                content_sha256="1" * 64,
                duration_seconds=1.0,
                media_format="m4a",
            )
        )
        session.add(
            Run(
                id=run_id,
                recording_id="rec-1",
                workflow_name="meeting-decisions",
                workflow_version="1.0.0",
                state=RunState.RUNNING,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.add(
            RunStep(
                run_id=run_id,
                step_id="ingest",
                skill="transcribe",
                skill_version="1",
                position=0,
                state=StepState.SUCCEEDED,
            )
        )
        session.commit()


def test_a_done_step_carries_a_checkmark_not_only_a_colour(
    tmp_path: Path, client: TestClient
) -> None:
    """The three shapes must read without colour: a marker icon each."""
    _insert_run_with_a_named_recording(tmp_path, "run-icons")

    body = client.get("/runs/run-icons/view").text

    # icon_check() (components/icons.html) draws this exact path.
    assert '<path d="M5 12l5 5 9-10"/>' in body


def test_the_runs_own_name_is_the_recordings_filename(tmp_path: Path, client: TestClient) -> None:
    _insert_run_with_a_named_recording(tmp_path, "run-name")

    body = client.get("/runs/run-name/view").text

    assert "<h1>Team retro, 24 Sep.m4a</h1>" in body
    # The concluded job's settings line, the workflow first.
    assert '<div class="vx-job-settings">\n  <span>Meeting decisions</span>' in body


def test_the_step_chain_sits_inside_the_same_card_as_the_header(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run_with_a_named_recording(tmp_path, "run-card")

    body = client.get("/runs/run-card/view").text

    assert '<div class="vx-card vx-run-card">' in body
    assert body.index('<div class="vx-card vx-run-card">') < body.index('id="vx-run-steps"')


def test_a_done_step_says_what_it_left_not_just_done(tmp_path: Path, client: TestClient) -> None:
    """`Transcript ready`, not `Done`, and the same words for run_page.js."""
    _insert_run_with_a_named_recording(tmp_path, "run-done")

    body = client.get("/runs/run-done/view").text

    chain = body[body.index('id="vx-run-steps"') : body.index('id="vx-done-labels"')]
    assert "Transcript ready" in chain and ">Done<" not in chain
    assert '<li data-step="ingest">Transcript ready</li>' in body
