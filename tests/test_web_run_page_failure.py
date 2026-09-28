"""Tests for GET /runs/{id}/view's failed-state banner and preview.

Split from test_web_run_page.py, which covers the page's static shell,
kept apart so neither file grows past the project's size limit.
test_web_run_page_memory_failure.py is the same split again, one level
further, for the memory-failure cases specifically.
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
from voxtrama.db.models.transcript import Segment, Transcript
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


def _insert_run(tmp_path: Path, run_id: str, state: RunState, **run_fields: object) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="Meeting Decisions",
                workflow_version="1.0.0",
                state=state,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                **run_fields,
            )
        )
        session.add(
            RunStep(
                run_id=run_id,
                step_id="extract",
                skill="extract",
                skill_version="1",
                position=0,
                state=StepState.FAILED if state == RunState.FAILED else StepState.SUCCEEDED,
            )
        )
        session.commit()


def test_a_failed_run_shows_the_failure_banner_and_no_terminal(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(
        tmp_path,
        "run-6",
        RunState.FAILED,
        error_code="generative_model_not_configured",
        error="no model",
    )

    body = client.get("/runs/run-6/view").text

    assert 'id="vx-run-failure"' in body
    assert "No summary model configured" in body
    assert 'id="vx-run-terminal"' not in body


def test_a_failed_run_shows_what_it_produced(tmp_path: Path, client: TestClient) -> None:
    _insert_run(
        tmp_path,
        "run-7",
        RunState.FAILED,
        error_code="generative_model_not_configured",
        error="no model",
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        transcript = Transcript(
            id="t-7",
            recording_id="r-7",
            language="en",
            model_name="whisper",
            model_revision="v1",
            hardware_profile="low",
            produced_by_run_id="run-7",
        )
        transcript.segments = [
            Segment(start=0.0, end=2.0, text="Good afternoon, everyone.", confidence=1.0)
        ]
        session.add(transcript)
        session.commit()

    body = client.get("/runs/run-7/view").text

    assert 'id="vx-run-produced"' in body
    assert "Good afternoon, everyone." in body
    # The job view's own bubbles, no arrow.
    assert '<li class="vx-turn vx-turn--left" data-start="0.0"' in body
    assert "View transcript</a>" in body


def test_a_failed_job_has_the_job_head_and_can_be_regenerated(
    tmp_path: Path, client: TestClient
) -> None:
    """The concluded job's head, «Regenerate job» included."""
    _insert_run(
        tmp_path,
        "run-8",
        RunState.FAILED,
        error_code="generative_model_unreachable",
        error="connection refused",
        recording_id="r-8",
    )

    body = client.get("/runs/run-8/view").text

    assert '<header class="vx-job-head">' in body
    assert 'action="/runs/run-8/regenerate"' in body
    assert "No summary model reachable" in body
