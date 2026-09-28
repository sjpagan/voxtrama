"""Tests for GET /runs/{id}/events resuming run.log from `?last_event_id=`.

The defect this closes: a fresh page load tails run.log for its own first
paint (api.routes.run_page), then opens this same route's SSE connection,
which used to start reading run.log from byte 0 regardless, resending every
line the page had just rendered. See fakes/events_client.py's docstring for
why httpx.AsyncClient, not fastapi.testclient.TestClient.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fakes.events_client import get_events_with_writer, insert_run
from fastapi import FastAPI
from sqlalchemy import Engine

import voxtrama.api.routes.run_events as run_events_module
from voxtrama.db.models.run import RunState
from voxtrama.engine.progress_file import write_progress
from voxtrama.engine.progress_state import ProgressState


def _write_log_line(runs_dir: Path, run_id: str, msg: str) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {"ts": "2026-09-26T05:20:00.000Z", "logger": "voxtrama.engine.run", "msg": msg}
    )
    with (run_dir / "run.log").open("a") as handle:
        handle.write(line + "\n")


def _log_events(text: str) -> list[dict]:
    """Every `log` message's own `data:`, in order, with `progress` ones dropped."""
    events = []
    for block in text.split("\n\n"):
        if not block.startswith("event: log"):
            continue
        data_line = next(line for line in block.split("\n") if line.startswith("data: "))
        events.append(json.loads(data_line[len("data: ") :]))
    return events


def _finish(runs_dir: Path, run_id: str) -> None:
    write_progress(
        runs_dir, ProgressState(run_id=run_id, state="succeeded", step_total=1, step_index=0)
    )


def test_a_fresh_connection_with_no_offset_gets_everything_already_in_run_log(
    events_app: tuple[FastAPI, Engine, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, engine, runs_dir = events_app
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    insert_run(engine, "run-1", RunState.RUNNING)
    _write_log_line(runs_dir, "run-1", "run started")

    actions = [lambda: _finish(runs_dir, "run-1")]
    response = get_events_with_writer(app, "run-1", actions, delay=0.05)

    lines = [line for event in _log_events(response.text) for line in event["lines"]]
    assert lines == [
        {"instant": "2026-09-26T05:20:00.000Z", "clock": "05:20:00", "message": "Job started"}
    ]


def test_a_connection_with_last_event_id_does_not_repeat_what_it_already_has(
    events_app: tuple[FastAPI, Engine, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact reproduction: a page that already rendered these two
    lines must not see them a second time over the wire."""
    app, engine, runs_dir = events_app
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    insert_run(engine, "run-1", RunState.RUNNING)
    _write_log_line(runs_dir, "run-1", "run started")
    _write_log_line(runs_dir, "run-1", "step started")
    already_shown = (runs_dir / "run-1" / "run.log").stat().st_size

    response = get_events_with_writer(
        app,
        "run-1",
        [lambda: _finish(runs_dir, "run-1")],
        delay=0.05,
        params={"last_event_id": already_shown},
    )

    assert _log_events(response.text) == []


def test_a_line_written_after_the_offset_still_arrives(
    events_app: tuple[FastAPI, Engine, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, engine, runs_dir = events_app
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    insert_run(engine, "run-1", RunState.RUNNING)
    _write_log_line(runs_dir, "run-1", "run started")
    already_shown = (runs_dir / "run-1" / "run.log").stat().st_size

    def _advance_then_finish() -> None:
        _write_log_line(runs_dir, "run-1", "step started")
        _finish(runs_dir, "run-1")

    response = get_events_with_writer(
        app,
        "run-1",
        [_advance_then_finish],
        delay=0.05,
        params={"last_event_id": already_shown},
    )

    lines = [line for event in _log_events(response.text) for line in event["lines"]]
    assert lines == [
        {"instant": "2026-09-26T05:20:00.000Z", "clock": "05:20:00", "message": "step started"}
    ]


def test_the_log_events_own_id_is_the_byte_offset_a_reconnect_would_resume_from(
    events_app: tuple[FastAPI, Engine, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`event: log` carries an `id:` line: what a real EventSource
    reconnect echoes back as `Last-Event-ID`, and log_tail_for reads the
    same way as `?last_event_id=` (the query-string tests above): it must
    be the exact byte offset RunLogTail itself would resume from, not an
    arbitrary counter of its own."""
    app, engine, runs_dir = events_app
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    insert_run(engine, "run-1", RunState.RUNNING)
    _write_log_line(runs_dir, "run-1", "run started")

    actions = [lambda: _finish(runs_dir, "run-1")]
    response = get_events_with_writer(app, "run-1", actions, delay=0.05)

    block = next(b for b in response.text.split("\n\n") if b.startswith("event: log"))
    event_id = next(line for line in block.split("\n") if line.startswith("id: "))[len("id: ") :]
    assert int(event_id) == (runs_dir / "run-1" / "run.log").stat().st_size
