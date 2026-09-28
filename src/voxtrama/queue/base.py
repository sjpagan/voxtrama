"""The Queue interface every backend, real or test double, must satisfy.

No import of rq or redis belongs in this file: it is the boundary the
core depends on, not an implementation of it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from voxtrama.queue.job import JobId, JobState, Progress


@runtime_checkable
class Queue(Protocol):
    """A job queue: submit work, and observe, cancel or probe it."""

    def submit(
        self, run_id: str, job_timeout: int | None = None, job_id: JobId | None = None
    ) -> JobId:
        """Enqueue the execution of an existing Run, returning its job id.

        `job_timeout` is the number of seconds the job may run before the
        backend kills it. None lets the backend fall back to its own
        default, which a caller should only do when it has nothing better:
        every real Run has a Recording whose duration lets one be computed.

        `job_id`, when given, is used as the queue job's id instead of one
        the backend would otherwise invent: engine.enqueue.enqueue_run
        generates it and writes it to Run.job_id before submitting, so the
        two never disagree about which job is executing which Run.
        """
        ...

    def submit_download(self, weight_key: str, job_id: JobId | None = None) -> JobId:
        """Enqueue a background download of one weight set's own files.

        Not a Run: the guided setup, and now the permanent /models library
        too, download a model before any Recording exists to attach one
        to. A second submit-like method, rather than forcing this through
        `submit()` (which resolves the queue job straight to a Run's id),
        keeps that resolution honest instead of inventing a fake Run to
        carry a download through it.

        `weight_key` is one of the three hardware profiles or
        "ecapa" (worker.tasks.download_model_job resolves either
        into the WeightSet it names), never a hardware profile alone,
        since ECAPA is not one and must not be made to pretend it is.
        """
        ...

    def status(self, job_id: JobId) -> JobState:
        """Return the current state of the given job."""
        ...

    def cancel(self, job_id: JobId) -> None:
        """Request cancellation of the given job."""
        ...

    def progress(self, job_id: JobId) -> Progress:
        """Return the current progress of the given job."""
        ...

    def ping(self) -> None:
        """Raise QueueUnavailable if the queue backend cannot be reached."""
        ...
