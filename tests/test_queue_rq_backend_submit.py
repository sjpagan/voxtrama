"""RQBackend.submit forwards a caller-given job_id to RQ.

Split from test_queue_rq_backend.py, which deliberately never mocks the
redis client: it proves QueueUnavailable against a real, unreachable
connection. Observing which job_id reaches RQ's own enqueue() needs the
opposite: no real broker involved, since the connection error would fire
before anything about the call's arguments could be checked.
"""

from __future__ import annotations

import pytest

from voxtrama.queue.job import JobId
from voxtrama.queue.rq_backend import RQBackend

# Same as test_queue_rq_backend.py: unreachable, but never dialled
# here, since backend._queue.enqueue is replaced before submit() runs.
_UNREACHABLE_REDIS_URL = "redis://localhost:1/0"


def test_submit_passes_the_given_job_id_to_rq(monkeypatch: pytest.MonkeyPatch) -> None:
    """The defect this closes: nothing used to write Run.job_id, so RQ's
    own invented id was the only one a caller could ever have used.
    """
    backend = RQBackend(_UNREACHABLE_REDIS_URL)
    received: dict[str, object] = {}

    def fake_enqueue(_name: str, *args: object, **kwargs: object) -> object:
        received.update(kwargs)
        return type("FakeJob", (), {"id": kwargs["job_id"]})()

    monkeypatch.setattr(backend._queue, "enqueue", fake_enqueue)

    result = backend.submit("some-run-id", job_id=JobId("chosen-job-id"))

    assert received["job_id"] == "chosen-job-id"
    assert result == "chosen-job-id"
