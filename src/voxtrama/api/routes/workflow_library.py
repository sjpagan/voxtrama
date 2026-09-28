"""GET /workflows: the Workflows page.

The three system workflows as cards, the custom one the edition allows
or the card that creates it, and the detail of the selected one under
the grid. `transcribe-only` is not a workflow on this page: it is
the new-job form's «Transcription only» option.

Editing a step's own skill is POST /workflows/{name}/steps
(workflow_edit.py); creating, editing and deleting the custom workflow
are api.routes.workflow_custom.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.routes.job_create import TRANSCRIBE_ONLY
from voxtrama.api.routes.workflow_choices import workflow_choices_for
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.config.settings import Settings
from voxtrama.edition import current_policy
from voxtrama.engine.catalog import WorkflowNotFoundError, list_workflow_names, load_named_workflow
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import build_offer, failed_offer, sidebar_items, stored_theme, theme_choices
from voxtrama.rendering.workflow_library import (
    CustomSlots,
    WorkflowCard,
    WorkflowDetail,
    workflow_card,
    workflow_detail,
)
from voxtrama.workflow.custom_limit import custom_workflow_names
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.errors import WorkflowError

router = APIRouter()

PATH = "/workflows"

# The system workflows in this order, the custom one after them.
_SYSTEM_ORDER = ("meeting-decisions", "lesson-companion", "research-interview")


def _names() -> list[str]:
    names = [name for name in list_workflow_names() if name != TRANSCRIBE_ONLY]
    return sorted(names, key=lambda name: (name not in _SYSTEM_ORDER, _rank(name), name))


def _rank(name: str) -> int:
    return _SYSTEM_ORDER.index(name) if name in _SYSTEM_ORDER else len(_SYSTEM_ORDER)


def _card(name: str, settings: Settings, custom: list[str]) -> tuple[WorkflowCard, Workflow | None]:
    """The card for `name`, and the Workflow behind it (None when it will not load)."""
    system = name not in custom
    try:
        workflow = load_named_workflow(name)
    except (WorkflowNotFoundError, WorkflowError) as exc:
        return WorkflowCard(offer=failed_offer(name, str(exc)), system=system, skills=()), None
    choices = workflow_choices_for(workflow)
    offer = build_offer(workflow, choices, settings.hardware_profile, settings.ollama_model)
    return workflow_card(workflow, offer, system), workflow


def _library(settings: Settings, selected: str | None) -> dict[str, object]:
    custom = custom_workflow_names()
    loaded = {name: _card(name, settings, custom) for name in _names()}
    names = list(loaded)
    chosen = selected if selected in names else (names[0] if names else None)
    detail: WorkflowDetail | None = None
    if chosen is not None:
        card, workflow = loaded[chosen]
        detail = workflow_detail(workflow, card.offer, card.system) if workflow else None
    return {
        "cards": [card for card, _ in loaded.values()],
        "selected": chosen,
        "detail": detail,
        "slots": CustomSlots(allowed=current_policy().custom_workflows, used=len(custom)),
        "system_names": [name for name in names if name not in custom],
    }


@router.get(PATH, response_class=HTMLResponse)
def workflow_library_page(
    session: DbDep, settings: SettingsDep, translator: TranslatorDep, workflow: str | None = None
) -> HTMLResponse:
    """Every workflow's card, and `workflow`'s detail (the first one when none is named)."""
    template = templates_environment.get_template("pages/workflow_library.html")
    return HTMLResponse(
        template.render(
            **page_context(
                session,
                translator,
                settings=settings,
                nav_items=sidebar_items("workflows"),
                **_library(settings, workflow),
                theme_choices=theme_choices(stored_theme(session)),
                origin=PATH,
            )
        )
    )
