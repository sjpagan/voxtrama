"""Public surface of the queue package.

RQBackend is not reexported here: importing it pulls in rq
and redis, and voxtrama.queue is also what core code imports (queue.base,
queue.job). Adapters and entrypoints import it directly from
voxtrama.queue.rq_backend.

For the same reason, entrypoints do not share a single queue factory:
api/deps.py and cli/commands/run.py each build their own RQBackend from
settings, rather than the CLI importing api/deps. There is no
dependency arrow between two entrypoints.
"""

from voxtrama.queue.base import Queue
from voxtrama.queue.errors import JobNotFound, JobTimeoutError, QueueError, QueueUnavailable
from voxtrama.queue.job import JobId, JobState, Progress

__all__ = [
    "Queue",
    "JobId",
    "JobState",
    "Progress",
    "QueueError",
    "JobNotFound",
    "QueueUnavailable",
    "JobTimeoutError",
]
