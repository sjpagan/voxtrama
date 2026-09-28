"""Test for GET /runs/{id}/events following a `running` run to its final state.

Split from test_runs_api_events.py: this needs a concurrent writer task
advancing progress.json while the request is in flight, the already-final
tests there do not. Two siblings, same reason plus the file-size limit:
test_runs_api_events_dedup.py (an unchanged state, no duplicate events) and
test_runs_api_events_reconnect.py (current state, not passed). See
fakes/events_client.py's docstring for the shared scaffolding and why
httpx.AsyncClient, not fastapi.testclient.TestClient.
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


def test_events_follow_a_running_run_to_its_final_state(
    events_app: tuple[FastAPI, Engine, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, engine, runs_dir = events_app
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    insert_run(engine, "run-1", RunState.RUNNING)
    write_progress(
        runs_dir, ProgressState(run_id="run-1", state="running", step_total=2, step_index=0)
    )

    def _advance() -> None:
        write_progress(
            runs_dir, ProgressState(run_id="run-1", state="running", step_total=2, step_index=1)
        )

    def _finish() -> None:
        write_progress(
            runs_dir, ProgressState(run_id="run-1", state="succeeded", step_total=2, step_index=1)
        )

    response = get_events_with_writer(app, "run-1", [_advance, _finish], delay=0.05)

    events = parse_events(response.text)
    assert [e["step_index"] for e in events] == [0, 1, 1]
    assert [e["state"] for e in events] == ["running", "running", "succeeded"]
    assert [e["final"] for e in events] == [False, False, True]
