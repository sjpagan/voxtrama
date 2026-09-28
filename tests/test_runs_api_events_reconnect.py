"""Test for GET /runs/{id}/events on a reconnection mid-course.

Split from test_runs_api_events_progress.py, which was over the project's size
limit with this test included: unrelated to the size limit alone, this one
is also a distinct claim worth isolating ("current state, not the ones
already passed") from "progression" and "no duplicate events", which its
siblings cover. See fakes/events_client.py's docstring for the shared
scaffolding and why httpx.AsyncClient, not fastapi.testclient.TestClient.
"""

from __future__ import annotations

import pytest
from fakes.events_client import get_events_with_writer, insert_run, parse_events
from fastapi import FastAPI
from sqlalchemy import Engine

import voxtrama.api.routes.run_events as run_events_module
from voxtrama.db.models.run import RunState
from voxtrama.engine.progress_file import write_progress
from voxtrama.engine.progress_state import ProgressState


def test_events_of_a_reconnection_start_from_the_current_state(
    events_app: tuple[FastAPI, Engine, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, engine, runs_dir = events_app
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    insert_run(engine, "run-1", RunState.RUNNING)
    write_progress(
        runs_dir, ProgressState(run_id="run-1", state="running", step_total=2, step_index=0)
    )
    write_progress(
        runs_dir, ProgressState(run_id="run-1", state="running", step_total=2, step_index=1)
    )

    def _finish() -> None:
        write_progress(
            runs_dir, ProgressState(run_id="run-1", state="succeeded", step_total=2, step_index=1)
        )

    # A fresh connection to a run already mid-course: it must see step 1,
    # the current state, never step 0: "resume from now, not from
    # the start".
    response = get_events_with_writer(app, "run-1", [_finish], delay=0.05)

    events = parse_events(response.text)
    assert [e["step_index"] for e in events] == [1, 1]
