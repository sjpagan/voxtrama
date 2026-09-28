"""Tests for GET /runs/{id}/view's live terminal panel.

Split from test_web_run_page.py, which covers the page's static shell,
kept apart so neither file grows past the project's size limit. Same
file-backed database shape as that file's own `client` fixture.
"""

from __future__ import annotations

import json
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


def _write_run_log(tmp_path: Path, run_id: str, events: list[dict]) -> None:
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run.log").write_text("\n".join(json.dumps(event) for event in events) + "\n")


def test_a_running_run_shows_the_terminal_panel_with_its_log_lines(
    tmp_path: Path, client: TestClient
) -> None:
    """The live page's own terminal panel, fed by the run's real run.log."""
    _insert_run(tmp_path, "run-5", RunState.RUNNING)
    event = {
        "ts": "2026-09-25T23:31:49.000Z",
        "logger": "voxtrama.engine.preparation",
        "msg": "step started",
    }
    _write_run_log(tmp_path, "run-5", [event])

    body = client.get("/runs/run-5/view").text

    assert 'id="vx-run-terminal" data-run-id="run-5">' in body  # no `hidden`: this run is live
    assert '<time datetime="2026-09-25T23:31:49.000Z" data-local="clock">23:31:49</time>' in body
    assert "23:31:49</time>  step started" in body
    assert 'id="vx-run-failure"' not in body


def test_a_terminal_panel_reads_only_the_last_n_lines_at_first_paint(
    tmp_path: Path, client: TestClient
) -> None:
    """api.routes.run_page.LOG_TAIL_LINES: a fresh page load never shows the
    whole file, only its own tail."""
    _insert_run(tmp_path, "run-11", RunState.RUNNING)
    events = [
        {"ts": "2026-09-25T00:00:00.000Z", "logger": "voxtrama.engine.run", "msg": f"line {i}"}
        for i in range(250)
    ]
    _write_run_log(tmp_path, "run-11", events)

    body = client.get("/runs/run-11/view").text

    assert "line 0</span>" not in body
    assert "line 249</span>" in body


def test_a_final_runs_log_stays_closed_without_a_stop_button(
    tmp_path: Path, client: TestClient
) -> None:
    """A job that is over keeps its log, closed, with nothing
    left to stop. `cancelled`: a succeeded run gets its result section
    and a failed one its banner, both with the same closed log below."""
    _insert_run(tmp_path, "run-12", RunState.CANCELLED)
    event = {
        "ts": "2026-09-25T23:31:49.000Z",
        "logger": "voxtrama.engine.run",
        "msg": "run started",
    }
    _write_run_log(tmp_path, "run-12", [event])

    body = client.get("/runs/run-12/view").text

    assert 'id="vx-run-terminal"' not in body and 'id="vx-run-stop"' not in body
    assert '<details class="vx-card vx-terminal" id="vx-run-log">' in body
    assert "23:31:49</time>  Job started" in body


def test_the_activity_log_names_the_step_that_starts(tmp_path: Path, client: TestClient) -> None:
    """A reader's words, not the engine's."""
    _insert_run(tmp_path, "run-13", RunState.RUNNING)
    event = {
        "ts": "2026-09-25T23:31:49.000Z",
        "logger": "voxtrama.engine.preparation",
        "msg": "step started",
        "step": "diarize",
    }
    _write_run_log(tmp_path, "run-13", [event])

    body = client.get("/runs/run-13/view").text

    assert ">Activity</h2>" in body
    assert "23:31:49</time>  Identifying speakers..." in body
