"""Closes a Run stuck in `running` because the worker executing it is gone.

A run lasts minutes to hours, and in that window a `docker compose down`, an
OOM kill of the `worker` container or a machine reboot are ordinary events.
The process dies, and the Run it was executing never gets to close itself:
nothing is left running that could write `interrupted` to it, so it would
sit in `running` forever. The queue is asked instead of guessing from how long a
Run has been running. See reconcile_manifest.py for
why the manifest is rewritten from what the database still knows instead
of from nothing. The writing (database, manifest, progress file) lives in
reconcile_close.py. This module only decides what a `running` Run should
become.

Not engine.failure.fail_run: a Run stuck this way did not fail on its
workflow's terms (no step returned a bad value, no skill raised), so
reporting it as `failed` would name the wrong cause.

Not every Run this closes was abandoned. One whose job the queue reports
as `cancelled` was stopped deliberately, by api.routes.run_cancel asking
the queue to kill it, and closes as `cancelled`, not `interrupted`.
Confusing the two would repeat the mistake this module avoids with
`failed`: a Run the user asked to stop is not a Run whose worker died.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.run import Run, RunState
from voxtrama.engine.reconcile_close import close_run
from voxtrama.queue.base import Queue
from voxtrama.queue.errors import JobNotFound, QueueUnavailable
from voxtrama.queue.job import JobId, JobState

logger = logging.getLogger(__name__)

_ALIVE_JOB_STATES = frozenset({JobState.PENDING, JobState.RUNNING})


def reconcile_orphan_runs(session: Session, queue: Queue, into: list[Run] | None = None) -> int:
    """Close every `running` Run whose queue job no longer supports it.

    Returns how many were closed. Stops, and closes nothing more, the
    moment the queue cannot answer at all (QueueUnavailable). A Run in
    `running` is orphaned only if the job executing it is provably gone,
    and an unreachable queue proves nothing. Closing runs on that silence
    would be the worse mistake.
    """
    runs_dir = get_paths(get_settings().data_dir).runs_dir
    running = session.scalars(select(Run).where(Run.state == RunState.RUNNING)).all()
    closed = 0
    for run in running:
        try:
            target_state = _closing_state(queue, run.job_id)
        except QueueUnavailable:
            logger.warning("queue unavailable: reconciliation stopped, %d run(s) closed", closed)
            break
        if target_state is not None:
            close_run(session, runs_dir, run, target_state)
            closed += 1
            if into is not None:  # engine.auto_resume starts these again
                into.append(run)
    return closed


def _closing_state(queue: Queue, job_id: str | None) -> RunState | None:
    """What a Run left in `running` should become, given what the queue says.

    None means still alive: `job_id` is `pending` or `running`, so someone
    is still executing it (even with more than one worker). A null
    `job_id` closes as `interrupted` outright: since job ids are
    written up front, every new Run gets a job_id before it is enqueued, so a null one can
    only belong to a Run created before that change, and there is nothing
    to ask the queue about. Otherwise the queue's state decides between
    the two ways a `running` Run stops being alive. `cancelled` means
    someone asked for this
    (api.routes.run_cancel). `succeeded`, `failed` or JobNotFound mean the
    worker running it is gone, with nothing more specific to say.
    """
    if job_id is None:
        return RunState.INTERRUPTED
    try:
        state = queue.status(JobId(job_id))
    except JobNotFound:
        return RunState.INTERRUPTED
    if state in _ALIVE_JOB_STATES:
        return None
    if state == JobState.CANCELLED:
        return RunState.CANCELLED
    return RunState.INTERRUPTED
