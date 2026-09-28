"""POST /runs/{id}/retry names the failed job it replaces once it succeeds."""

from __future__ import annotations

from pathlib import Path

from fakes.queue import InMemoryQueue
from test_run_regenerate import _client, _new_run, queue  # noqa: F401 - the fixture

from voxtrama.db.models.run import RunState


def test_a_retry_names_the_failed_attempt_it_replaces(tmp_path: Path, queue: InMemoryQueue) -> None:  # noqa: F811
    client = _client(tmp_path, queue, RunState.FAILED)

    client.post("/runs/run-1/retry", follow_redirects=False)

    assert _new_run(tmp_path).replaces_run_id == "run-1"
