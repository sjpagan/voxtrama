"""Tests for the run page's step chain: measured HTML, not eyeballed.

Split from test_web_run_page.py (same fixture shape), kept apart so
neither file grows past the project's size limit (its own docstring already
explains that split for test_web_run_page_labels.py). Split again from
test_web_run_page_chain_markers.py, for the same reason.
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

# Two steps done, one running, two still pending: "3 of 5".
CHAIN_STEPS = [
    ("ingest", StepState.SUCCEEDED),
    ("transcribe", StepState.SUCCEEDED),
    ("speakers", StepState.RUNNING),
    ("extract", StepState.PENDING),
    ("validate", StepState.PENDING),
]


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


def _insert_run_in_progress(tmp_path: Path, run_id: str) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="meeting-decisions",
                workflow_version="1.0.0",
                state=RunState.RUNNING,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        for position, (step_id, state) in enumerate(CHAIN_STEPS):
            session.add(
                RunStep(
                    run_id=run_id,
                    step_id=step_id,
                    skill="transcribe",
                    skill_version="1",
                    position=position,
                    state=state,
                )
            )
        session.commit()


def test_the_chain_tells_the_current_step_apart_from_done_and_future_ones(
    tmp_path: Path, client: TestClient
) -> None:
    """Measured, not eyeballed: a run in progress
    shows its done steps checked, its current one running, and the rest untouched.
    """
    _insert_run_in_progress(tmp_path, "run-chain")

    body = client.get("/runs/run-chain/view").text

    assert 'data-step-id="ingest" data-step-state="succeeded"' in body
    assert 'data-step-id="transcribe" data-step-state="succeeded"' in body
    assert 'data-step-id="speakers" data-step-state="running"' in body
    assert 'data-step-id="extract" data-step-state="pending"' in body
    assert 'data-step-id="validate" data-step-state="pending"' in body


def test_the_step_count_is_the_step_now_running_out_of_the_total(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run_in_progress(tmp_path, "run-count")

    body = client.get("/runs/run-count/view").text

    assert '<span id="vx-run-progress-current">3</span>' in body
    progress = body.split('id="vx-run-progress">')[1].split("</span>", 1)[1]
    assert "5" in progress.split("</span>")[0]


def test_the_step_count_is_gone_once_the_run_is_final(tmp_path: Path, client: TestClient) -> None:
    """Measured on a real run: "3 of 3 · Failed" reads as all three
    done, not two succeeded and one failed. The state beside it already says
    it, so a final run shows no count at all rather than one that misleads.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id="run-final",
                workflow_name="meeting-decisions",
                workflow_version="1.0.0",
                state=RunState.FAILED,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        for position, (step_id, state) in enumerate(
            [
                ("ingest", StepState.SUCCEEDED),
                ("transcribe", StepState.SUCCEEDED),
                ("extract", StepState.FAILED),
            ]
        ):
            session.add(
                RunStep(
                    run_id="run-final",
                    step_id=step_id,
                    skill="transcribe",
                    skill_version="1",
                    position=position,
                    state=state,
                )
            )
        session.commit()

    body = client.get("/runs/run-final/view").text

    assert 'id="vx-run-progress"' not in body
    assert 'id="vx-run-state"' in body
