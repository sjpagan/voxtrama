"""GET /runs/{id}/events: the SSE stream of a run's progress.

A design choice, not a workaround for how FastAPI happens to behave: `DbDep`
(api/deps.get_db) is a `yield` dependency, and in the installed FastAPI
(0.141.1, see fastapi/routing.py's `request_response`) it does stay open
for the whole streaming response, closed only once `StreamingResponse` has
sent its last byte. That is an implementation detail this route does not
lean on either way. A generator that can run for as long as a run itself
(minutes, for a generative step) must not hold a database session open for
that whole time regardless of when the framework would let it get away with
that, so the `Run` row is read exactly once, here in the route function,
and only the plain values that survive it (id, state) cross into the
generator. Everything the generator reads afterwards is progress.json,
never the database (see `_generate` and `run_event_view.run_event_from_run`).

Two ways this stream ends on its own:

* the `Run` row is already final when the client connects. A stale
  progress.json must not keep it attached to a run that already ended, so
  this is answered from the database, not the file.
* `progress.json` itself reaches a final state while the client is
  watching. Every path to a final state writes that file
  (engine/run.py, engine/failure.py, engine/reconcile_close.py), so this is
  never left to poll a run that will never say so.

A run that is merely `pending`, with no progress.json yet, is neither: it
is still in queue, and the engine's reconciliation closes it, not this
route. So it polls and sends `: keepalive` comments instead, which is the
one place this module writes to the wire without
going through `format_event`.

There is also a second event, `log` (run_log_stream.log_event), never gated by
_dedup_key: a step silent on progress.json still shows run.log advancing.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.routes.run_event_view import RunEvent, run_event_from_progress, run_event_from_run
from voxtrama.api.routes.run_log_stream import log_event, log_tail_for, poll_once
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.api.sse import KEEPALIVE, format_event
from voxtrama.config.paths import get_paths
from voxtrama.db.models.run import is_final
from voxtrama.engine.progress_state import ProgressState

router = APIRouter()

# Same value as cli.progress_view.POLL_SECONDS: no reason to watch a run
# faster or slower depending on who is watching it. A module constant, not
# a default argument, so a test can `monkeypatch.setattr` it. A default
# argument is bound at import time and a patch after that would not reach it.
POLL_SECONDS = 0.4
# How long the wire can stay silent before a keepalive comment fills it.
# Not "how long progress.json can be missing": a generative step
# publishes `ceiling_seconds` once and then has no loop to report from for
# minutes, so the file exists and does not change for as long as a
# queued run has no file at all. Both are silence on the wire, and a proxy
# does not care which one it is. Unrelated to cli.progress_view.SILENCE_
# SECONDS, which gives up watching. This route never gives up: the
# engine's reconciliation is what in the end closes a run no worker ever picks up.
KEEPALIVE_SECONDS = 15.0


def _dedup_key(state: ProgressState) -> ProgressState:
    """`state` with its timestamp blanked out: what changed, not when it was republished.

    engine.progress_file.activity_reporter writes on every callback tick
    once `percent` reaches 100 or `total` is unknown (its own guard only
    skips a repeated *percentage*): same content, fresh `updated_at`, one
    write per tick. Comparing full ProgressState objects would read every
    one of those as a change and send an SSE client a burst of identical
    `progress` events.
    """
    return replace(state, updated_at="")


async def _generate(
    runs_dir: Path, run_id: str, first_event: RunEvent | None, request: Request
) -> AsyncIterator[str]:
    """Yield SSE messages for one run, until it is final or the client leaves.

    `first_event` set means the Run was already final at connection time:
    sent alone, without touching progress.json or run.log. Otherwise the
    loop reads both (run_log_stream.poll_once). Progress's own dedup
    makes the first read always count even when it repeats the previous
    cycle's value. `log` bypasses that dedup entirely.
    """
    if first_event is not None:
        yield format_event("progress", first_event.model_dump_json(), first_event.updated_at)
        return
    last: ProgressState | None = None
    last_sent = time.monotonic()
    log_tail = log_tail_for(runs_dir, run_id, request)
    while True:
        if await request.is_disconnected():
            return
        state, new_lines = await poll_once(runs_dir, run_id, log_tail)
        progressed = False
        if new_lines:
            yield log_event(new_lines, log_tail.offset)
            last_sent = time.monotonic()
        if state is not None and _dedup_key(state) != last:
            last = _dedup_key(state)
            event = run_event_from_progress(state)
            yield format_event("progress", event.model_dump_json(), state.updated_at)
            last_sent = time.monotonic()
            progressed = True
            if event.final:
                return
        if not new_lines and not progressed and time.monotonic() - last_sent >= KEEPALIVE_SECONDS:
            last_sent = time.monotonic()
            yield KEEPALIVE
        await asyncio.sleep(POLL_SECONDS)


@router.get(
    "/runs/{run_id}/events",
    responses={
        status.HTTP_200_OK: {
            "content": {"text/event-stream": {"schema": RunEvent.model_json_schema()}},
            "description": "One `progress` event per state change, until the run is final.",
        }
    },
)
async def run_events_route(run_id: str, request: Request, session: DbDep, settings: SettingsDep):
    """Stream `run_id`'s progress. 404 before the stream opens if it does not exist."""
    run = get_run_or_404(run_id, session)
    first_event = run_event_from_run(run) if is_final(run.state) else None
    runs_dir = get_paths(settings.data_dir).runs_dir
    return StreamingResponse(
        _generate(runs_dir, run_id, first_event, request),
        media_type="text/event-stream",
        # A buffering proxy turns a stream into a file that only arrives at
        # the end. Cache-Control tells an HTTP cache the same
        # thing, and X-Accel-Buffering is the header nginx listens
        # for to skip its own buffering on this response.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
