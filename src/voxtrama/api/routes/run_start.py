"""POST /recordings/{recording_id}/runs: start a Run from the workflow-choice
panel, and land on it instead of rendering it in place.

The model is api/routes/profile.py: POST then a 303 redirect, because
reloading a page that was itself the result of a form submission
re-submits it, and "confirm form resubmission" is a question nobody can
answer well after a Run has already been created and enqueued. Here the
redirect target is not the form's own page but /runs/{id}/view,
the running page: the same destination GET /runs/{id}'s own home-page
row already opens, and the one place a run belongs once it exists.

Creation and submission both go through engine.enqueue.enqueue_run, the
one place that sequence is written (same as api/routes/run_create.py
uses for the JSON POST /runs): this route does not duplicate it, only
translates its two failure shapes (a rejected choice, an unreachable
queue) into a request failure the same way run_create.py already does
for its own JSON callers. The two mappings read alike because they
answer the same question, not because one imports the other. Each route
here owns only the failures its own request can produce.

`hardware_profile` and `generative_model` are the two fixed selects every
workflow offers or not. A per-step skill alternative (the third
kind of run choice) has no fixed name (meeting-decisions.yaml declares one
today, another workflow might declare several or none), so those arrive
as `step_skill__<step_id>` fields, read from the raw form rather than
declared as named parameters, and turned back into RunChoices.step_skills.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from voxtrama.api.deps import DbDep, QueueDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.recording_lookup import get_recording_or_404
from voxtrama.api.routes.workflow_lookup import load_workflow_or_422
from voxtrama.db.models.run import Run
from voxtrama.db.people import local_user
from voxtrama.engine.enqueue import enqueue_run
from voxtrama.queue.base import Queue
from voxtrama.queue.errors import QueueUnavailable
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import SkillRef, Workflow
from voxtrama.workflow.rejection import ChoicesRejected

router = APIRouter()

_STEP_SKILL_PREFIX = "step_skill__"


def _run_choices(hardware_profile: str, generative_model: str, form: FormData) -> RunChoices:
    """Build RunChoices from the panel's selects. A blank one means "chose nothing"."""
    step_skills: dict[str, SkillRef] = {}
    for key, value in form.multi_items():
        if not key.startswith(_STEP_SKILL_PREFIX) or not value:
            continue
        skill, _, skill_version = str(value).rpartition(":")
        step_skills[key[len(_STEP_SKILL_PREFIX) :]] = SkillRef(
            skill=skill, skill_version=skill_version
        )
    try:
        return RunChoices(
            hardware_profile=hardware_profile or None,
            generative_model=generative_model or None,
            step_skills=step_skills,
        )
    except ValidationError as exc:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_failed",
            title="The run choices do not match the expected shape",
            detail=str(exc),
        ) from exc


def _enqueue_or_error(
    session: Session,
    queue: Queue,
    workflow_name: str,
    workflow: Workflow,
    recording_id: str,
    choices: RunChoices,
    created_by: str | None,
    reused_from: str | None = None,
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
            reused_from_run_id=reused_from,
        )
    except QueueUnavailable as exc:
        # Same as run_create.py's own _enqueue_or_error: the Run stays
        # `pending`, a genuine request the queue failed to pick up.
        raise ProblemException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="queue_unavailable",
            title="The queue is unavailable",
            detail=str(exc),
        ) from exc
    except ChoicesRejected as exc:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="rule_rejected",
            title="The run choices were refused by a declared rule",
            detail=str(exc),
        ) from exc
    return run


@router.post("/recordings/{recording_id}/runs")
async def start_run_route(
    recording_id: str,
    request: Request,
    session: DbDep,
    queue: QueueDep,
    workflow_name: Annotated[str, Form()],
    hardware_profile: Annotated[str, Form()] = "",
    generative_model: Annotated[str, Form()] = "",
) -> RedirectResponse:
    """Enqueue a Run of `workflow_name` on `recording_id`, then redirect to its own page."""
    get_recording_or_404(recording_id, session)
    workflow = load_workflow_or_422(workflow_name)
    form = await request.form()
    choices = _run_choices(hardware_profile, generative_model, form)
    created_by = local_user(session).id
    run = _enqueue_or_error(
        session, queue, workflow_name, workflow, recording_id, choices, created_by
    )
    return RedirectResponse(f"/runs/{run.id}/view", status_code=status.HTTP_303_SEE_OTHER)
