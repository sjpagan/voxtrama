"""Tests for engine.vitality.run_vitality: what the queue's own answer means.

The classification mirrors engine.reconcile's own table without
writing anything. These tests check the reading, not any side effect,
since run_vitality never has one.
"""

from __future__ import annotations

from fakes.queue import InMemoryQueue, _JobRecord

from voxtrama.engine.vitality import Vitality, run_vitality
from voxtrama.queue.job import JobId, JobState, Progress


def _set_job_state(queue: InMemoryQueue, job_id: str, state: JobState) -> None:
    queue._jobs[JobId(job_id)] = _JobRecord(state=state, progress=Progress(0, 0, ""))


def test_a_null_job_id_is_gone(queue: InMemoryQueue) -> None:
    assert run_vitality(queue, None) == Vitality.GONE


def test_a_pending_job_is_alive(queue: InMemoryQueue) -> None:
    _set_job_state(queue, "job-1", JobState.PENDING)
    assert run_vitality(queue, "job-1") == Vitality.ALIVE


def test_a_running_job_is_alive(queue: InMemoryQueue) -> None:
    _set_job_state(queue, "job-2", JobState.RUNNING)
    assert run_vitality(queue, "job-2") == Vitality.ALIVE


def test_a_succeeded_job_is_gone(queue: InMemoryQueue) -> None:
    _set_job_state(queue, "job-3", JobState.SUCCEEDED)
    assert run_vitality(queue, "job-3") == Vitality.GONE


def test_a_cancelled_job_is_gone(queue: InMemoryQueue) -> None:
    """This module does not distinguish `cancelled` from a dead worker (its own docstring):
    a page only needs to know whether to show "still going", and either
    way the answer here is no.
    """
    _set_job_state(queue, "job-4", JobState.CANCELLED)
    assert run_vitality(queue, "job-4") == Vitality.GONE


def test_a_job_the_queue_has_never_heard_of_is_gone(queue: InMemoryQueue) -> None:
    # Never registered on the fake queue: queue.status raises JobNotFound,
    # the same as RQBackend does for an id Redis has evicted (its TTL).
    assert run_vitality(queue, "job-ghost") == Vitality.GONE


def test_an_unreachable_queue_is_unknown_not_gone(queue: InMemoryQueue) -> None:
    """Restraint: on a fact that is not there, this says so rather than
    guessing either way.
    """
    queue.available = False
    assert run_vitality(queue, "job-5") == Vitality.UNKNOWN
