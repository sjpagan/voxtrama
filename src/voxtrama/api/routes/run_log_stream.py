"""The run.log half of GET /runs/{id}/events: the log side of the same poll.

Split out of run_events.py to stay under the project's file-length limit.
That module's own docstring explains why the terminal panel's `log` event
shares its connection with `progress` instead of opening a second one.

Where this same connection starts reading run.log from matters: the page's
own first paint (api.routes.run_page) already tailed up to LOG_TAIL_LINES of
it, and a RunLogTail that always starts at byte 0 sent that same content
again the moment the SSE connection opened: the whole terminal panel,
doubled, worse the longer a run runs. log_tail_for below is where that
resume point is decided, the same way the page's own render decided where
its tail left off.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import Request

from voxtrama.api.sse import format_event
from voxtrama.engine.progress_file import read_progress
from voxtrama.engine.progress_state import ProgressState
from voxtrama.logs.run_file import RUN_LOG_FILENAME
from voxtrama.logs.tail import RunLogTail


def log_event(lines: list[str], offset: int) -> str:
    """A `log` SSE message carrying the lines RunLogTail picked up this poll.

    `offset` (RunLogTail.offset, after the read that produced `lines`)
    becomes this message's own `id:` line: what a reconnecting
    EventSource echoes back as `Last-Event-ID`, and what log_tail_for below
    reads to resume a fresh connection from the same point instead of 0.
    """
    return format_event("log", json.dumps({"lines": lines}), str(offset))


def log_tail_for(runs_dir: Path, run_id: str, request: Request) -> RunLogTail:
    """A RunLogTail seeded at wherever `request` says it already has read to.

    `Last-Event-ID` first: what a real EventSource reconnect sends on its
    own, matching the `id:` line log_event writes above. A first connection
    cannot set that header (no prior message to echo), so api.routes.run_page
    passes the same value along as `?last_event_id=` on the very URL its own
    template builds the EventSource from, for that one case. Read here, either source is honoured
    identically.
    """
    raw = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    offset = 0
    if raw is not None:
        try:
            offset = int(raw)
        except ValueError:
            offset = 0
    return RunLogTail(runs_dir / run_id / RUN_LOG_FILENAME, offset)


async def poll_once(
    runs_dir: Path, run_id: str, log_tail: RunLogTail
) -> tuple[ProgressState | None, list[str]]:
    """One read of progress.json and one of run.log, both off the event loop's own thread.

    Bundled in one awaited call, not two, so run_events._generate reads as
    the state machine it is rather than two interleaved ones: neither read
    depends on the other, both belong to the same poll tick.
    """
    state = await asyncio.to_thread(read_progress, runs_dir, run_id)
    lines = await asyncio.to_thread(log_tail.read_new_lines)
    return state, lines
