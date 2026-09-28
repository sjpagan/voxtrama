"""Tests for GET /runs/{id}/events staying alive on the wire while nothing new arrives.

Split from the other test_runs_api_events*.py files for a reason beyond
the project's size limit: both streams here never close on their own (that is
the behaviour under test), and httpx.ASGITransport (used elsewhere in this
package, see fakes/events_client.py's docstring) buffers an entire ASGI
response before handing any of it back, which cannot represent a stream
that keeps going forever. So these drive run_events._generate directly,
the same coroutine the route hands to StreamingResponse, instead of going
through an HTTP round trip at all.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import voxtrama.api.routes.run_events as run_events_module
from voxtrama.api.sse import KEEPALIVE
from voxtrama.engine.progress_file import write_progress
from voxtrama.engine.progress_state import ProgressState


class _NeverDisconnects:
    """A stand-in for fastapi.Request: these tests drive the generator without an app."""

    # log_tail_for reads both off a real Request; empty here is
    # exactly what a fresh connection with nothing to resume looks like.
    headers: dict[str, str] = {}
    query_params: dict[str, str] = {}

    async def is_disconnected(self) -> bool:
        return False


async def _collect(runs_dir: Path, run_id: str, count: int) -> list[str]:
    generator = run_events_module._generate(runs_dir, run_id, None, _NeverDisconnects())
    chunks = []
    async for chunk in generator:
        chunks.append(chunk)
        if len(chunks) == count:
            # Stopping the test, not the server: a real client would simply
            # disconnect. This route must not be the one to give up on a
            # queued or silent run (reconciliation is),
            # so nothing here should make the generator return on its own
            # before this.
            await generator.aclose()
            break
    return chunks


def test_events_of_a_pending_run_send_keepalives_and_stay_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(run_events_module, "KEEPALIVE_SECONDS", 0.03)

    # tmp_path doubles as runs_dir: no progress.json exists under it for
    # "run-1", the same as a run nothing has picked up yet.
    chunks = asyncio.run(_collect(tmp_path, "run-1", count=3))

    assert chunks == [KEEPALIVE] * 3


def test_events_of_a_silent_generative_step_send_keepalives_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A generative step publishes `ceiling_seconds` once and then has no loop to
    report from for minutes: progress.json exists and does not change for
    that whole time. Regression: the earlier
    keepalive only fired when progress.json was *missing*, so this exact case
    (the file present and silent) left the wire quiet for the whole wait.
    """
    monkeypatch.setattr(run_events_module, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(run_events_module, "KEEPALIVE_SECONDS", 0.03)
    write_progress(
        tmp_path,
        ProgressState(run_id="run-1", state="running", step_total=1, ceiling_seconds=120.0),
    )

    chunks = asyncio.run(_collect(tmp_path, "run-1", count=3))

    assert chunks[0].startswith("event: progress\n")
    assert chunks[1:] == [KEEPALIVE, KEEPALIVE]
