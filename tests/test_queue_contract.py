"""Contract test: the in-memory Queue double satisfies the Queue protocol."""

from __future__ import annotations

import pytest
from fakes.queue import InMemoryQueue

from voxtrama.queue.base import Queue
from voxtrama.queue.errors import QueueUnavailable
from voxtrama.queue.job import JobState


def test_fake_queue_satisfies_the_protocol(queue: InMemoryQueue) -> None:
    assert isinstance(queue, Queue)


def test_submit_status_progress_cancel_roundtrip(queue: InMemoryQueue) -> None:
    job_id = queue.submit("some-run-id")
    assert queue.status(job_id) == JobState.SUCCEEDED
    progress = queue.progress(job_id)
    assert progress.total_steps == 0
    queue.cancel(job_id)
    assert queue.status(job_id) == JobState.CANCELLED


def test_ping_raises_when_marked_unavailable(queue: InMemoryQueue) -> None:
    queue.available = False
    with pytest.raises(QueueUnavailable):
        queue.ping()
