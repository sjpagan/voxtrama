"""Tests for engine.enqueue.enqueue_run: create-then-submit, and which name survives."""

from __future__ import annotations

import pytest
from fakes.queue import InMemoryQueue
from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run
from voxtrama.engine.enqueue import enqueue_run
from voxtrama.queue.errors import QueueUnavailable
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Workflow


def _workflow(name: str) -> Workflow:
    return Workflow(
        name=name,
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[],
    )


def test_enqueue_run_creates_a_pending_run_and_submits_it(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run, job_id = enqueue_run(db_session, queue, "catalog-name", _workflow("catalog-name"))

    assert run.state == JobState.PENDING
    # The fake queue runs its (no-op) job inline: reaching SUCCEEDED here
    # proves submit() was called, not only that create_run() was.
    assert queue.status(job_id) == JobState.SUCCEEDED


def test_run_job_id_is_set_and_matches_what_the_queue_received(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run, job_id = enqueue_run(db_session, queue, "catalog-name", _workflow("catalog-name"))

    assert run.job_id is not None
    assert run.job_id == job_id
    # queue.status would raise JobNotFound if the queue had used a job_id
    # of its own invention instead of the one it was given.
    assert queue.status(run.job_id) == JobState.SUCCEEDED


def test_run_keeps_its_job_id_when_submit_fails(db_session: Session, queue: InMemoryQueue) -> None:
    """If submit() raises, the Run this closes the window on must
    still be reachable, in `pending`, with its job_id already written,
    not left the way collecting job_id from submit()'s return value would
    have: committed, but with no way to tell which job was meant for it.
    """
    queue.available = False

    with pytest.raises(QueueUnavailable):
        enqueue_run(db_session, queue, "catalog-name", _workflow("catalog-name"))

    run = db_session.query(Run).one()
    assert run.state == JobState.PENDING
    assert run.job_id is not None


def test_run_workflow_name_is_the_lookup_name_not_the_yaml_field(
    db_session: Session, queue: InMemoryQueue
) -> None:
    """Regression: a workflow file whose own `name:` differs from the
    name it was looked up by (e.g. intervista.yaml declaring `name:
    colloquio`) must not leak that internal name into Run.workflow_name.
    engine.run.execute_run re-resolves the workflow from Run.workflow_name
    through the same catalogue lookup a worker uses (`{name}.yaml`). A Run
    stored under the wrong name can be created but can never be run.
    """
    workflow = _workflow("colloquio")  # the YAML's own `name:` field

    run, _job_id = enqueue_run(db_session, queue, "intervista", workflow)

    assert run.workflow_name == "intervista"
