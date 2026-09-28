"""POST /workflows/{name}/steps: change a step's own skill from the
library's own Advanced panel: the one thing someone may rewrite
from the interface, and only among the alternatives the
workflow itself already declares (its `allows.skills`, the same
list api.routes.workflow_choices already computes for a run's own
choice: no second "what is compatible" answer invented for editing).

Validated in full before a byte is written: an edit that leaves the
document invalid names which step and why, and
voxtrama.workflow.document_write.save_document is never even called:
the "never invalid" rule editing requires, on top of that module's own
round-trip safety net.

Always the user's own copy: save_document builds its path from data_dir
alone, so editing one of the four workflows the package ships
creates a covering copy in the data directory rather than touching the
file inside the image: the same precedence workflow.document.
document_roots already gives a read, so the shipped file is never at
risk of being overwritten by this route.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from starlette.datastructures import FormData

from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.workflow_choices import workflow_choices_for
from voxtrama.api.routes.workflow_library import PATH
from voxtrama.api.routes.workflow_lookup import load_workflow_or_422
from voxtrama.engine.builtin import BUILTIN_SKILLS
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.document_write import save_document
from voxtrama.workflow.errors import WorkflowError
from voxtrama.workflow.loader import validate_workflow

router = APIRouter()

_STEP_SKILL_PREFIX = "step_skill__"


def _allowed_alternatives(workflow: Workflow) -> dict[str, set[tuple[str, str]]]:
    """Every step's own declared alternatives, keyed by step id:
    the same set a run's own choice panel offers, reused rather than a
    second "what may this step become" computed for editing.
    """
    choices = workflow_choices_for(workflow)
    return {
        step.step_id: {(ref.skill, ref.skill_version) for ref in step.skills}
        for step in choices.steps
    }


def _edited_workflow(workflow: Workflow, form: FormData) -> Workflow:
    """`workflow` with each `step_skill__<id>` field applied to that step,
    or unchanged where the field is blank. A value that step does not
    list among its own alternatives is rejected before validation ever
    runs, so a tampered form is refused for what it is, not folded
    into a generic "invalid workflow" message naming no cause.
    """
    allowed = _allowed_alternatives(workflow)
    steps = []
    for step in workflow.steps:
        raw = form.get(f"{_STEP_SKILL_PREFIX}{step.id}")
        if not raw:
            steps.append(step)
            continue
        skill, _, skill_version = str(raw).rpartition(":")
        if (skill, skill_version) not in allowed.get(step.id, set()):
            raise ProblemException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="rule_rejected",
                title="That skill is not one this step allows",
                detail=f"steps: '{step.id}' does not allow skill '{raw}'",
            )
        steps.append(step.model_copy(update={"skill": skill, "skill_version": skill_version}))
    return workflow.model_copy(update={"steps": steps})


@router.post("/workflows/{name}/steps")
async def save_workflow_steps(name: str, request: Request) -> RedirectResponse:
    """Apply the Advanced panel's own edits to `name`, or write nothing."""
    workflow = load_workflow_or_422(name)
    form = await request.form()
    edited = _edited_workflow(workflow, form)
    try:
        validate_workflow(edited, BUILTIN_SKILLS)
    except WorkflowError as exc:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_failed",
            title="The edited workflow is not valid",
            detail=str(exc),
        ) from exc
    save_document("workflows", name, edited)
    return RedirectResponse(f"{PATH}?workflow={name}", status_code=status.HTTP_303_SEE_OTHER)
