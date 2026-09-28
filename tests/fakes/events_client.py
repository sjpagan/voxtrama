"""Shared scaffolding for GET /runs/{id}/events tests.

Every test_runs_api_events*.py file drives the same real app through the
same HTTP client; only the assertion differs from file to file, which is
what "divide by context" is about. The scaffolding itself is not
a context split, it is one thing, so it lives here once. The queue double
lives once in fakes/queue.py for the same reason.

httpx.AsyncClient against httpx.ASGITransport, not fastapi.testclient.
TestClient: this route calls `request.is_disconnected()` from inside its
own generator, and Starlette's StreamingResponse.__call__ (spec_version <
2.4, starlette/responses.py lines 265-280) *also* consumes `receive()`
concurrently, in its own `listen_for_disconnect` task, to detect a
disconnect the generator itself never checked for. TestClient's synchronous
`receive()` (starlette/testclient.py) only has one message to give out
before it falls back to waiting on the response being complete, so the
second of those two readers blocks on an event that only the first
reader's own request finishing can set. Two readers on one channel is the
deadlock; httpx.ASGITransport's asyncio-native `receive()` does not have
that problem.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.run import Run, RunState


def build_app(tmp_path: Path) -> tuple[FastAPI, Engine, Path]:
    """A real app wired to a file-backed database and `tmp_path` as its data dir."""
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    return app, engine, get_paths(tmp_path).runs_dir


def insert_run(engine: Engine, run_id: str, state: RunState, **overrides: object) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="demo",
                workflow_version="1.0.0",
                state=state,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                **overrides,
            )
        )
        session.commit()


def parse_events(text: str) -> list[dict]:
    """One dict per SSE message, parsed from its `data:` line."""
    events = []
    for block in text.split("\n\n"):
        if not block:
            continue
        data_line = next(line for line in block.split("\n") if line.startswith("data: "))
        events.append(json.loads(data_line[len("data: ") :]))
    return events


def get_events(app: FastAPI, run_id: str, **kwargs: object) -> httpx.Response:
    """GET the stream once. `**kwargs` (e.g. `params={"last_event_id": ...}`)
    pass straight through to httpx. Every existing caller sends none."""

    async def _do() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(f"/runs/{run_id}/events", **kwargs)

    return asyncio.run(_do())


def get_events_with_writer(
    app: FastAPI, run_id: str, actions: list[Callable[[], None]], delay: float, **kwargs: object
) -> httpx.Response:
    """GET the stream while `actions` run, one every `delay` seconds, concurrently.

    `asyncio.create_task` before the request, not a background thread: the
    generator's own `await asyncio.sleep(POLL_SECONDS)` is what hands
    control back to this event loop between polls, which is what lets
    `actions` run at all while the same request is still open. `**kwargs`
    (e.g. `params={"last_event_id": ...}`) pass straight through to httpx,
    the same as get_events above.
    """

    async def _do() -> httpx.Response:
        async def writer() -> None:
            for action in actions:
                await asyncio.sleep(delay)
                action()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            task = asyncio.create_task(writer())
            response = await client.get(f"/runs/{run_id}/events", **kwargs)
            await task
            return response

    return asyncio.run(_do())
