"""The one place a Run is created and handed to the queue.

The CLI and the API both reach a Run the same way: create it, then submit it.
Before this module existed only the CLI did that, in cli/commands/run.py; the
API route would otherwise have written a second copy of the same sequence,
a second copy that any change to `Run.job_id` would then have to touch twice.

Run.job_id is generated here, not read back from submit()'s return value.
Reading it back would leave a window where the Run is already committed
(visible to a worker or a reconciler) without knowing which job is
executing it. Writing it in the same commit that creates the Run
closes that window instead of managing it.

Takes the Queue protocol (queue.base.Queue), not RQBackend, so this stays
testable without one running.

The caller must already have loaded and validated the Workflow, not just
its name, because the CLI and the route fail differently on a name that
does not resolve (a message on stderr versus a 422).

enqueue_run's `workflow_name` argument is kept separate from `workflow`,
and is not `workflow.name`: it is the name the workflow was *looked up*
by, while `workflow.name` is whatever the YAML document says about
itself, which nothing checks against the file it lives in.
engine.run.execute_run re-resolves the workflow from Run.workflow_name
through that same catalogue lookup, so it has to be the lookup name.

enqueue_run also checks `choices` against `workflow` and its skills before
creating anything, for the same reason job_id lives here
and not in the CLI or the route. ChoicesRejected propagates up uncaught.
The route and the CLI translate it differently, as with WorkflowError.

engine.builtin.BUILTIN_SKILLS is imported at module level, not inside
enqueue_run: nothing in engine.builtin reaches back into engine.enqueue.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState
from voxtrama.engine.builtin import BUILTIN_SKILLS
from voxtrama.engine.choice_check import check_choices
from voxtrama.engine.timeout import job_timeout_for
from voxtrama.queue.base import Queue
from voxtrama.queue.job import JobId
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Workflow


def create_run(
    session: Session,
    workflow_name: str,
    workflow_version: str,
    recording_id: str | None = None,
    workflow: Workflow | None = None,
    job_id: str | None = None,
    choices: RunChoices | None = None,
    created_by: str | None = None,
    reused_from_run_id: str | None = None,
) -> Run:
    """Create a Run in pending state and commit it, so it can be returned.

    `workflow` only sizes the job_timeout's download budget. Moved
    here from engine.run: this is the one place a Run is created,
    and engine.run.execute_run has nothing to do with creation.

    `choices` is written onto the Run in this same commit, not a second one
    after it. job_id follows the same reasoning, but here
    the failure mode is worse: a machine that dies between two commits
    would leave a Run that silently runs with the global settings. None
    stays None on the column: a Run that chose nothing must read that way,
    not as an empty RunChoices serialised to `{}`.

    `created_by` is a user id the caller already resolved, not looked up
    here: engine is core and cannot call db.people.local_user. Stays None
    if the caller does not pass it. A Run without a known author is a
    possible row, not an error.

    `reused_from_run_id` is what this run *asked for*, written in
    this same commit for the same reason `choices` is above.
    """
    run = Run(
        workflow_name=workflow_name,
        workflow_version=workflow_version,
        recording_id=recording_id,
        state=RunState.PENDING,
        job_id=job_id,
        job_timeout_seconds=job_timeout_for(session, recording_id, workflow),
        choices=choices.model_dump(mode="json") if choices is not None else None,
        created_by=created_by,
        reused_from_run_id=reused_from_run_id,
    )
    session.add(run)
    session.commit()
    return run


def enqueue_run(
    session: Session,
    queue: Queue,
    workflow_name: str,
    workflow: Workflow,
    recording_id: str | None = None,
    choices: RunChoices | None = None,
    created_by: str | None = None,
    reused_from_run_id: str | None = None,
) -> tuple[Run, JobId]:
    """Create a Run and submit it to the queue, in that order, not the other way.

    See the module docstring for why `workflow_name` is kept separate from
    `workflow`, and for why job_id is generated up front here instead of
    read back from submit()'s return value.

    `choices` is checked before anything is created: a rejected choice must
    leave no Run behind, not one that gets created and then discarded.
    `choices or RunChoices()` mirrors ExecutionContext.choices. check_choices
    already treats an empty RunChoices as one that cannot contradict
    anything. `reused_from_run_id` only names the
    source run, unvalidated here like `recording_id`: cli.commands.run
    fails before calling this.

    The Run must be committed before submit() is called: a worker can pick
    the job up the instant it is enqueued, and if the Run is not yet visible
    in the database at that moment the worker finds nothing to execute.

    If submit() raises, the Run still exists, in `pending` state, with its
    job_id already set. That is correct: the run was genuinely requested,
    and deleting it here would hide a queue failure by discarding a request
    that was never at fault. The caller decides what to tell whoever
    asked, but the Run stays.
    """
    check_choices(choices or RunChoices(), workflow, BUILTIN_SKILLS)
    job_id = JobId(str(uuid.uuid4()))
    run = create_run(
        session,
        workflow_name,
        workflow_version=workflow.version,
        recording_id=recording_id,
        workflow=workflow,
        job_id=job_id,
        choices=choices,
        created_by=created_by,
        reused_from_run_id=reused_from_run_id,
    )
    queue.submit(run.id, job_timeout=run.job_timeout_seconds, job_id=job_id)
    return run, job_id
