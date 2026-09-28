"""RQBackend.cancel stops a job a worker is running.

RQ's Job.cancel() only marks a job as canceled: a job already running on a
worker carried on to the end, and «Stop job» did nothing. A running job is
now stopped with RQ's stop-job command, which kills the process running
it. Redis is faked at the two calls the backend makes.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from rq.exceptions import InvalidJobOperation

from voxtrama.queue import rq_backend
from voxtrama.queue.job import JobId


class _Job:
    def __init__(self, status: str, worker: str | None) -> None:
        self.id, self._status, self.worker_name, self.canceled = "job-1", status, worker, False

    def get_status(self) -> str:
        return self._status

    def cancel(self) -> None:
        self.canceled = True


def _backend(job: _Job) -> rq_backend.RQBackend:
    backend = rq_backend.RQBackend.__new__(rq_backend.RQBackend)
    backend._redis = SimpleNamespace()
    backend._fetch = lambda job_id: job
    return backend


def test_a_running_job_is_killed_not_only_marked(monkeypatch: pytest.MonkeyPatch) -> None:
    stopped: list[str] = []
    monkeypatch.setattr(rq_backend, "send_stop_job_command", lambda redis, jid: stopped.append(jid))
    job = _Job("started", "worker-1")

    _backend(job).cancel(JobId("job-1"))

    assert stopped == ["job-1"]
    assert not job.canceled


def test_a_waiting_job_is_only_marked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rq_backend, "send_stop_job_command", lambda *a: pytest.fail("killed"))
    job = _Job("queued", None)

    _backend(job).cancel(JobId("job-1"))

    assert job.canceled


def test_a_job_that_ended_meanwhile_is_marked(monkeypatch: pytest.MonkeyPatch) -> None:
    def _gone(redis, jid):
        raise InvalidJobOperation("Job is not currently executing")

    monkeypatch.setattr(rq_backend, "send_stop_job_command", _gone)
    job = _Job("started", "worker-1")

    _backend(job).cancel(JobId("job-1"))

    assert job.canceled
