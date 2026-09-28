"""RQ/Redis-backed implementation of the Queue protocol.

Every module but this one reaches the queue through queue.base.Queue, with
one deliberate exception: engine.timeout_message also imports rq, because
RQ's timeout fires via a signal wherever the job happens to be executing,
and only the code running at that moment can recognise it (see its
docstring).
"""

from __future__ import annotations

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue as RQQueue
from rq import Worker
from rq.command import send_stop_job_command
from rq.exceptions import InvalidJobOperation
from rq.job import Job as RQJob

from voxtrama.queue.errors import JobNotFound, QueueUnavailable
from voxtrama.queue.job import JobId, JobState, Progress

# Falls back only when a caller submits without a computed job_timeout:
# RQ's own default is 180 seconds, which is what let a run longer
# than about four minutes die mid-transcription with no explanation. This
# fallback is generous rather than tight, for the same reason a real
# job_timeout is: a job killed mid-way loses the work already done, while a
# worker held longer just sits idle.
_FALLBACK_JOB_TIMEOUT_SECONDS = 3600

_STATE_MAP = {
    "queued": JobState.PENDING,
    "started": JobState.RUNNING,
    "finished": JobState.SUCCEEDED,
    "failed": JobState.FAILED,
    "stopped": JobState.CANCELLED,
    "canceled": JobState.CANCELLED,
}


class RQBackend:
    """Queue implementation backed by a single RQ queue over Redis."""

    def __init__(self, redis_url: str, queue_name: str = "voxtrama") -> None:
        self._redis = Redis.from_url(redis_url)
        self._queue = RQQueue(
            queue_name, connection=self._redis, default_timeout=_FALLBACK_JOB_TIMEOUT_SECONDS
        )

    def submit(
        self, run_id: str, job_timeout: int | None = None, job_id: JobId | None = None
    ) -> JobId:
        """Enqueue the execution of an existing Run, by id, over RQ.

        The job target is given by string, not by reference: importing
        voxtrama.worker.tasks here would make an adapter depend on an
        entrypoint, against the project's dependency direction. RQ resolves
        the string when the worker picks the job up.

        `job_id`, when given, is handed to RQ's own `job_id` kwarg so
        the id RQ assigns the job is the one the caller already wrote to
        Run.job_id, instead of RQ inventing its own that nothing recorded.
        """
        try:
            job = self._queue.enqueue(
                "voxtrama.worker.tasks.execute_run_job",
                run_id,
                job_timeout=job_timeout,
                job_id=str(job_id) if job_id is not None else None,
            )
        except RedisError as exc:
            raise QueueUnavailable(str(exc)) from exc
        return JobId(job.id)

    def submit_download(self, weight_key: str, job_id: JobId | None = None) -> JobId:
        """Enqueue a background weights download, by string target like submit()."""
        try:
            job = self._queue.enqueue(
                "voxtrama.worker.tasks.download_model_job",
                weight_key,
                job_id=str(job_id) if job_id is not None else None,
            )
        except RedisError as exc:
            raise QueueUnavailable(str(exc)) from exc
        return JobId(job.id)

    def _fetch(self, job_id: JobId) -> RQJob:
        try:
            job = self._queue.fetch_job(str(job_id))
        except RedisError as exc:
            raise QueueUnavailable(str(exc)) from exc
        if job is None:
            raise JobNotFound(str(job_id))
        return job

    def status(self, job_id: JobId) -> JobState:
        """Return the current state of the given job."""
        return _STATE_MAP.get(self._fetch(job_id).get_status(), JobState.PENDING)

    def cancel(self, job_id: JobId) -> None:
        """Stop the given job: a waiting one never runs, a running one is killed.

        RQ's own Job.cancel() only marks a job: a job already running kept
        running to the end («Stop job» did nothing). A
        job a worker is executing is stopped with RQ's stop-job command,
        which kills the process running it.
        """
        job = self._fetch(job_id)
        if job.get_status() == "started" and job.worker_name:
            try:
                send_stop_job_command(self._redis, job.id)
                return
            except InvalidJobOperation:
                pass  # it finished in between: marking it is all that is left
        job.cancel()

    def progress(self, job_id: JobId) -> Progress:
        """Return the current progress of the given job, from its RQ meta."""
        meta = self._fetch(job_id).meta or {}
        return Progress(
            current_step=meta.get("current_step", 0),
            total_steps=meta.get("total_steps", 0),
            message=meta.get("message", ""),
        )

    def ping(self) -> None:
        """Raise QueueUnavailable if Redis cannot be reached."""
        try:
            self._redis.ping()
        except RedisError as exc:
            raise QueueUnavailable(str(exc)) from exc


def serve_worker(redis_url: str, queue_name: str = "voxtrama") -> None:
    """Block, consuming jobs from the given RQ queue until stopped."""
    redis_conn = Redis.from_url(redis_url)
    Worker([queue_name], connection=redis_conn).work()
