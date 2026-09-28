"""POST /runs: create a Run and hand it to the queue.

Split out of runs.py because creating a Run and reading one are two
different subjects, and runs.py is already close to the project's file
size limit, the same reason recording_audio.py sits next to recordings.py.

Creation and submission both happen through engine.enqueue.enqueue_run, the
one place this sequence is written: the CLI of cli/commands/run.py
goes through the same function, so a fix or a future field (a job_id)
only has to land once.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from voxtrama.api.deps import DbDep, EngineDep, QueueDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.migration_gate import reject_unless_schema_current
from voxtrama.api.routes.workflow_lookup import load_workflow_or_422
from voxtrama.api.run_views import RunSummary, run_summary
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.people import local_user
from voxtrama.engine.enqueue import enqueue_run
from voxtrama.queue.base import Queue
from voxtrama.queue.errors import QueueUnavailable
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.rejection import ChoicesRejected

router = APIRouter()


class RunIn(BaseModel):
    """What starting a Run takes: which workflow, on which Recording, and what it chooses."""

    model_config = ConfigDict(extra="forbid")
    workflow_name: str
    recording_id: str
    choices: RunChoices | None = None
    # The name a person gives this run in the new-job form's `Job name`
    # field. See db.models.run.Run.label's own docstring for why it is
    # a plain column, not a RunChoices field: it decides nothing
    # engine.choice_check would refuse, so it does not belong where every
    # other field is checked against a workflow's own constraints.
    label: str | None = Field(default=None, max_length=200)


def _get_recording_or_404(recording_id: str, session: Session) -> Recording:
    recording = session.get(Recording, recording_id)
    if recording is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="The recording does not exist",
            detail=f"No recording with id {recording_id}",
        )
    return recording


def _enqueue_or_error(
    session: Session,
    queue: Queue,
    workflow_name: str,
    workflow: Workflow,
    recording_id: str,
    choices: RunChoices | None,
    created_by: str | None,
) -> Run:
    try:
        run, _job_id = enqueue_run(
            session,
            queue,
            workflow_name,
            workflow,
            recording_id=recording_id,
            choices=choices,
            created_by=created_by,
        )
    except QueueUnavailable as exc:
        # The Run this call created is not rolled back (see enqueue_run's
        # own docstring): it stays `pending`, a genuine request the queue
        # failed to pick up, not a request that never happened.
        raise ProblemException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="queue_unavailable",
            title="The queue is unavailable",
            detail=str(exc),
        ) from exc
    except ChoicesRejected as exc:
        # Raised by check_choices before enqueue_run creates anything:
        # no Run exists at this point, so there is nothing to
        # leave behind, unlike the QueueUnavailable case above. `detail`
        # carries str(exc) whole (every rejection ChoicesRejected
        # collected, joined by "; ") because it is the only thing that
        # names which skill, which field and which value refused the choice.
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="rule_rejected",
            title="The run choices were refused by a declared rule",
            detail=str(exc),
        ) from exc
    return run


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED, response_model=RunSummary)
def create_run_route(body: RunIn, session: DbDep, queue: QueueDep, engine: EngineDep) -> RunSummary:
    """Create a Run for `body.recording_id` on `body.workflow_name` and enqueue it.

    202, not 201: the Run row is created, but the work it
    describes has not started: a worker has not even picked the job up yet.
    """
    reject_unless_schema_current(engine)
    workflow = load_workflow_or_422(body.workflow_name)
    _get_recording_or_404(body.recording_id, session)
    created_by = local_user(session).id
    run = _enqueue_or_error(
        session, queue, body.workflow_name, workflow, body.recording_id, body.choices, created_by
    )
    if body.label is not None:
        # A second, separate commit rather than threaded through
        # enqueue_run (unlike choices/created_by/reused_from_run_id, which
        # must land in the same commit that creates the Run): a label
        # decides nothing engine.choice_check or execute_run reads, so a
        # crash between the two commits leaves a nameless run, never one
        # that silently ran with the wrong settings (see Run.label's own
        # docstring). Also keeps engine.enqueue, already at the project's line
        # limit, free of a field its own module has no use for.
        run.label = body.label
        session.commit()
    return run_summary(run)
