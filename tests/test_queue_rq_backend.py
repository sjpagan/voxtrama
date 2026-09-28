"""RQBackend against an unreachable Redis: every method must fail the same way.

No fakeredis in this project's dependencies, so "unreachable" is a real
connection refused, on a port nothing listens on, not a mock of the redis
client. ping() and _fetch() already translated RedisError into
QueueUnavailable; submit() did not, which is the defect this file covers.
"""

from __future__ import annotations

import pytest

from voxtrama.queue.errors import QueueUnavailable
from voxtrama.queue.job import JobId
from voxtrama.queue.rq_backend import RQBackend

# Port 1 is privileged and unassigned: nothing binds it in a test environment,
# so the connection is refused immediately instead of timing out.
_UNREACHABLE_REDIS_URL = "redis://localhost:1/0"


@pytest.fixture
def backend() -> RQBackend:
    return RQBackend(_UNREACHABLE_REDIS_URL)


def test_ping_raises_queue_unavailable(backend: RQBackend) -> None:
    with pytest.raises(QueueUnavailable):
        backend.ping()


def test_status_raises_queue_unavailable(backend: RQBackend) -> None:
    with pytest.raises(QueueUnavailable):
        backend.status(JobId("some-job-id"))


def test_submit_raises_queue_unavailable_not_a_bare_redis_error(backend: RQBackend) -> None:
    """The defect this closes: submit() used to let RedisError through raw."""
    with pytest.raises(QueueUnavailable):
        backend.submit("some-run-id")
