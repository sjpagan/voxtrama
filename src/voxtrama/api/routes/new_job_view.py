"""What the home's new-job form shows: workflows, defaults, choosable models.

The workflow cards are the system workflows plus the one custom workflow
the edition allows, never `transcribe-only`: that one is the
form's «Transcription only» option now. A workflow that will not
load is left out of the form rather than offered as a card nobody can
start. The library is where its reason is shown.

The first card is the one the library's «Run workflow» sent along, else
meeting-decisions, else the first in alphabetical order.
"""

from __future__ import annotations

from dataclasses import replace

from voxtrama.api.routes.job_create import TRANSCRIBE_ONLY
from voxtrama.api.routes.job_defaults import job_defaults, summary_models, transcription_models
from voxtrama.api.routes.workflow_choices import workflow_choices_for
from voxtrama.config.settings import Settings
from voxtrama.engine.catalog import WorkflowNotFoundError, list_workflow_names, load_named_workflow
from voxtrama.i18n.negotiation import negotiate_locale
from voxtrama.rendering import build_offer
from voxtrama.rendering.workflow_offers import WorkflowOffer
from voxtrama.workflow.errors import WorkflowError
from voxtrama.workflow.output_languages import OUTPUT_LANGUAGES

DEFAULT_WORKFLOW = "meeting-decisions"


def job_workflows(settings: Settings) -> list[WorkflowOffer]:
    """Every workflow a job can start on, as offers, the default one first."""
    offers = []
    for name in list_workflow_names():
        if name == TRANSCRIBE_ONLY:
            continue
        try:
            workflow = load_named_workflow(name)
        except (WorkflowNotFoundError, WorkflowError):
            continue
        choices = workflow_choices_for(workflow)
        offers.append(
            build_offer(workflow, choices, settings.hardware_profile, settings.ollama_model)
        )
    return sorted(offers, key=lambda offer: offer.name != DEFAULT_WORKFLOW)


def new_job_context(
    settings: Settings, requested: str | None, accept_language: str | None = None
) -> dict[str, object]:
    """The template context of the new-job form, with the recap in the browser's language."""
    workflows = job_workflows(settings)
    names = [offer.name for offer in workflows]
    selected = requested if requested in names else (names[0] if names else None)
    return {
        "job_workflows": workflows,
        "job_selected_workflow": selected,
        "job_defaults": replace(
            job_defaults(settings),
            output_language=negotiate_locale(OUTPUT_LANGUAGES, None, accept_language, None),
        ),
        "transcription_models": transcription_models(),
        "summary_models": summary_models(settings),
        "workflow_titles": {offer.name: offer.title for offer in workflows},
    }


def job_workflow_titles(settings: Settings) -> dict[str, str]:
    """Every workflow's readable title, `transcribe-only` included."""
    titles = {offer.name: offer.title for offer in job_workflows(settings)}
    try:
        titles[TRANSCRIBE_ONLY] = load_named_workflow(TRANSCRIBE_ONLY).title or TRANSCRIBE_ONLY
    except (WorkflowNotFoundError, WorkflowError):
        titles[TRANSCRIBE_ONLY] = TRANSCRIBE_ONLY
    return titles
