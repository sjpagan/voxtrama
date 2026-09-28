"""Tests for GET /runs/{id}/events not repeating an unchanged state.

Split from test_runs_api_events_progress.py, which was over the project's size
limit with this test included: unrelated to the limit alone, it is also a
distinct claim worth isolating from "progression": the same content read
twice, however it got onto disk, must produce one event, not two. See
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


def test_events_do_not_repeat_an_unwritten_state(
    events_app: tuple[FastAPI, Engine, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, engine, runs_dir = events_app
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    insert_run(engine, "run-1", RunState.RUNNING)
    write_progress(
        runs_dir, ProgressState(run_id="run-1", state="running", step_total=1, step_index=0)
    )

    def _finish() -> None:
        write_progress(
            runs_dir, ProgressState(run_id="run-1", state="succeeded", step_total=1, step_index=0)
        )

    # delay spans several POLL_SECONDS cycles with nothing written: without
    # this dedup, each of those cycles would repeat the same "running" event.
    response = get_events_with_writer(app, "run-1", [_finish], delay=0.05)

    events = parse_events(response.text)
    assert len(events) == 2


def test_events_do_not_repeat_a_rewrite_with_identical_content(
    events_app: tuple[FastAPI, Engine, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, engine, runs_dir = events_app
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    insert_run(engine, "run-1", RunState.RUNNING)
    write_progress(
        runs_dir, ProgressState(run_id="run-1", state="running", step_total=1, step_index=0)
    )

    def _rewrite_same_content() -> None:
        # A fresh ProgressState, same fields, a new `updated_at` (none given
        # explicitly): what engine.progress_file.activity_reporter writes
        # on every callback tick once percent reaches 100 or `total` is
        # unknown: its guard only skips a repeated *percentage*, so this is
        # one real write per tick, same content, different timestamp.
        write_progress(
            runs_dir, ProgressState(run_id="run-1", state="running", step_total=1, step_index=0)
        )

    def _finish() -> None:
        write_progress(
            runs_dir, ProgressState(run_id="run-1", state="succeeded", step_total=1, step_index=0)
        )

    response = get_events_with_writer(app, "run-1", [_rewrite_same_content, _finish], delay=0.05)

    events = parse_events(response.text)
    assert len(events) == 2
