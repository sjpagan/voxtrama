"""The step chain's own fallback for the moment right after `Start run`'s
redirect, before a single RunStep row exists yet.

Split from test_web_run_page_chain.py (same fixture shape, kept apart so
neither file grows past the project's size limit). That file's own docstring
already explains this split for two other files.

Measured on a real run: engine.progress.record_planned_steps writes RunStep
rows a beat after the worker picks the job up, not at `Start run`'s own
redirect. A person landing on the page inside that gap used to see no
chain at all, [data-step-id] absent from the DOM for 32 seconds while
RunStep already held three rows in the database.
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

# workflows/meeting-decisions.yaml's own three steps, real on disk,
# not a fixture workflow: the same file api.routes.run_page_
# planned_steps.planned_workflow_steps_for reads through engine.catalog.
_MEETING_DECISIONS_STEP_IDS = ["transcribe", "diarize", "extract_decisions"]


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


def _insert_run_with_no_steps(tmp_path: Path, run_id: str) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="meeting-decisions",
                workflow_version="2.0.0",
                state=RunState.RUNNING,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()


def test_a_running_run_with_no_run_step_yet_shows_its_workflow_own_steps(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run_with_no_steps(tmp_path, "run-race")

    body = client.get("/runs/run-race/view").text

    for step_id in _MEETING_DECISIONS_STEP_IDS:
        assert f'data-step-id="{step_id}" data-step-state="pending"' in body


def test_real_run_step_rows_win_over_the_workflow_fallback(
    tmp_path: Path, client: TestClient
) -> None:
    """Once RunStep rows exist, they take precedence: a step this run's own
    condition skipped must show `skipped`, a fact the workflow file alone
    cannot know, never shadowed back to `pending` by the fallback above.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id="run-real-rows",
                workflow_name="meeting-decisions",
                workflow_version="2.0.0",
                state=RunState.RUNNING,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        for position, (step_id, state) in enumerate(
            [
                ("transcribe", StepState.SUCCEEDED),
                ("diarize", StepState.SKIPPED),
                ("extract_decisions", StepState.RUNNING),
            ]
        ):
            session.add(
                RunStep(
                    run_id="run-real-rows",
                    step_id=step_id,
                    skill="transcribe",
                    skill_version="1",
                    position=position,
                    state=state,
                )
            )
        session.commit()

    body = client.get("/runs/run-real-rows/view").text

    assert 'data-step-id="diarize" data-step-state="skipped"' in body
    assert 'data-step-id="diarize" data-step-state="pending"' not in body
