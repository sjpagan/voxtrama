"""Tests for GET /runs/{id}/events when the run is already final, or missing.

A running run that progresses is tested separately, in
test_runs_api_events_progress.py: that file needs a concurrent writer
advancing progress.json while the stream is open, this one does not, and
keeping the two apart is also what keeps each file under the project's
file size limit.

The `events_app` fixture and the HTTP helpers below come from
fakes/events_client.py, shared by every test_runs_api_events*.py file. See
that module's docstring for why httpx.AsyncClient against
httpx.ASGITransport, not fastapi.testclient.TestClient.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fakes.events_client import get_events, insert_run, parse_events
from fastapi import FastAPI
from sqlalchemy import Engine

from voxtrama.db.models.run import RunState


@pytest.mark.parametrize(
    "state", [RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED, RunState.INTERRUPTED]
)
def test_events_of_an_already_final_run_close_after_one_event(
    events_app: tuple[FastAPI, Engine, object], state: RunState
) -> None:
    app, engine, _ = events_app
    insert_run(engine, "run-1", state, finished_at=datetime(2026, 1, 1, 0, 5, tzinfo=UTC))

    response = get_events(app, "run-1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    events = parse_events(response.text)
    assert len(events) == 1
    assert events[0]["state"] == state.value
    assert events[0]["final"] is True


def test_events_404_when_the_run_does_not_exist(
    events_app: tuple[FastAPI, Engine, object],
) -> None:
    app, _, _ = events_app

    response = get_events(app, "no-such-run")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "not_found"
