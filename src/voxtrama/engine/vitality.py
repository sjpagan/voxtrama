"""Whether the worker executing a `running` Run still exists, for a live page to show.

This answers "is the job behind this Run still alive" by asking the
queue instead of guessing from elapsed time. A Run's progress.json goes
quiet for minutes during a generative step by design (the docstring on
KEEPALIVE_SECONDS in api.routes.run_events says a step with a declared
ceiling "has no loop to report from for minutes"), so staleness of that
file cannot tell a legitimate wait from a dead worker. This module asks
the same question the same way, read-only. engine.reconcile.
reconcile_orphan_runs decides what a `running` Run becomes once its job
is provably gone, and commits that. An open page must not have that side
effect: a Run closes at the next worker startup, not on a page load.

Three answers. `ALIVE` when the queue reports the job
`pending` or `running`. `GONE` when it reports anything else, or does not
know the job (JobNotFound). `UNKNOWN` when the queue cannot be reached
(QueueUnavailable). When the fact is missing this says so instead of
guessing. Closing a run on a network hiccup would be a mistake, and so
would telling a page "still going" on the same silence.
"""

from __future__ import annotations

from enum import StrEnum

from voxtrama.queue.base import Queue
from voxtrama.queue.errors import JobNotFound, QueueUnavailable
from voxtrama.queue.job import JobId, JobState

_ALIVE_JOB_STATES = frozenset({JobState.PENDING, JobState.RUNNING})


class Vitality(StrEnum):
    """What the queue says, right now, about the job executing a `running` Run."""

    ALIVE = "alive"
    GONE = "gone"
    UNKNOWN = "unknown"


def run_vitality(queue: Queue, job_id: str | None) -> Vitality:
    """Classify `job_id` as reconciliation would, without writing anything.

    Takes a `Queue` and a bare id, never a `Session`. The signature makes a
    database write impossible from inside this function, since there is
    nothing to write through. api.routes.run_vitality, the one caller,
    reads a Run only to find its `job_id` and never touches it afterwards.

    A null `job_id` is always GONE, as in reconcile._closing_state: only a
    Run created before job ids were written up front lacks one, and there is nothing to
    ask the queue about. This does not tell `cancelled` apart from a worker
    that died on its own. That distinction decides what reconciliation
    *writes*, and a page asking "is this still going" has no write to make.
    """
    if job_id is None:
        return Vitality.GONE
    try:
        state = queue.status(JobId(job_id))
    except JobNotFound:
        return Vitality.GONE
    except QueueUnavailable:
        return Vitality.UNKNOWN
    return Vitality.ALIVE if state in _ALIVE_JOB_STATES else Vitality.GONE
