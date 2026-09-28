"""In-memory Queue double: executes jobs synchronously, no Redis required."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from voxtrama.queue.errors import JobNotFound, QueueUnavailable
from voxtrama.queue.job import JobId, JobState, Progress


@dataclass
class _JobRecord:
    state: JobState
    progress: Progress


class InMemoryQueue:
    """Test double for Queue: runs work inline, keeps state in a dict."""

    def __init__(self) -> None:
        self._jobs: dict[JobId, _JobRecord] = {}
        self.available = True

    def submit(
        self, run_id: str, job_timeout: int | None = None, job_id: JobId | None = None
    ) -> JobId:
        """Run the (no-op) job synchronously and record it as succeeded.

        Raises QueueUnavailable when `available` is False, same as ping():
        the real backend fails both the same way when Redis is unreachable
        (RQBackend.submit used to be the one method that did not).

        Uses the given `job_id` when the caller supplies one, the
        same as RQBackend does, rather than always inventing its own.
        """
        if not self.available:
            raise QueueUnavailable("fake queue marked unavailable")
        if job_id is None:
            job_id = JobId(str(uuid.uuid4()))
        self._jobs[job_id] = _JobRecord(
            state=JobState.SUCCEEDED,
            progress=Progress(current_step=0, total_steps=0, message="done"),
        )
        return job_id

    def submit_download(self, weight_key: str, job_id: JobId | None = None) -> JobId:
        """Same fake shape as submit(): recorded as done, nothing downloaded."""
        if not self.available:
            raise QueueUnavailable("fake queue marked unavailable")
        if job_id is None:
            job_id = JobId(str(uuid.uuid4()))
        self._jobs[job_id] = _JobRecord(
            state=JobState.SUCCEEDED,
            progress=Progress(current_step=0, total_steps=0, message="done"),
        )
        return job_id

    def _get(self, job_id: JobId) -> _JobRecord:
        """Look `job_id` up, the same way status/cancel/progress all do.

        Raises QueueUnavailable when `available` is False, same as
        submit() and ping(): RQBackend's own status/cancel/progress all
        reach Redis through fetch_job, so all three fail the same way when
        it is unreachable, not only submit() and ping().
        """
        if not self.available:
            raise QueueUnavailable("fake queue marked unavailable")
        try:
            return self._jobs[job_id]
        except KeyError:
            raise JobNotFound(str(job_id)) from None

    def status(self, job_id: JobId) -> JobState:
        """Return the current state of the given job."""
        return self._get(job_id).state

    def cancel(self, job_id: JobId) -> None:
        """Mark the given job as cancelled."""
        self._get(job_id).state = JobState.CANCELLED

    def progress(self, job_id: JobId) -> Progress:
        """Return the current progress of the given job."""
        return self._get(job_id).progress

    def ping(self) -> None:
        """Raise QueueUnavailable when `available` has been set to False."""
        if not self.available:
            raise QueueUnavailable("fake queue marked unavailable")
