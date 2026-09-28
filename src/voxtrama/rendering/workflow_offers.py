"""What the workflow-choice panel shows, per workflow.

Built from voxtrama.api.routes.workflow_choices.workflow_choices_for, the
one place hardware_profiles, generative_models and every step's allowed
alternatives are computed. Nothing is recomputed here. This
module only turns that answer, plus the Workflow it came from, into rows
a template lays out (the same split rendering.recordings and
rendering.runs follow).

A workflow that fails to load (a broken skill file, a malformed YAML)
must still appear instead of vanishing silently. failed_offer builds the
same WorkflowOffer shape from its name and the reason it did not load,
the same "say why, do not go quiet" rule diagnostics.machine applies to
a reading it could not take.

`hardware_profile_default` and `generative_model_default` carry what
already applies to a run that changes nothing: the installation's
VOXTRAMA_HARDWARE_PROFILE / VOXTRAMA_OLLAMA_MODEL (config.settings), read
by the route and passed in, not read here. Naming them, instead of
leaving the blank option unlabelled, lets a reader tell "as configured"
from "changed for this run". A step's default
has no installation-wide counterpart, so StepChoiceRow carries its
`default_label` straight from StepChoices.

`title` and `produces` are a fallback formatting rule and a
reading of the workflow's steps. Both live in rendering.workflow_produces,
split out once this file's line count required it.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.api.workflow_choices import WorkflowChoices
from voxtrama.rendering.workflow_produces import default_title, produces
from voxtrama.workflow.definition import SkillRef, Workflow


@dataclass(frozen=True)
class SkillOption:
    """One alternative a step's `allows.skills` offers, as a form can submit it."""

    value: str
    label: str


@dataclass(frozen=True)
class StepChoiceRow:
    """One step that offers a skill alternative. A step with none is left out entirely."""

    step_id: str
    default_label: str
    options: list[SkillOption]


@dataclass(frozen=True)
class WorkflowOffer:
    """One workflow, presented for what it produces and what a run on it may choose.
    `available=False` is a workflow shown, not hidden, with the reason it could not
    be offered.
    """

    name: str
    title: str
    version: str
    description: str
    available: bool
    unavailable_reason: str | None
    hardware_profiles: list[str]
    hardware_profile_default: str
    # None: no step restricts this choice, so the field is not offered.
    # []: some step restricts it and nothing survived every step's list at
    # once. Offered, empty, with its own reason (mirrors WorkflowChoices).
    generative_models: list[str] | None
    generative_model_default: str | None
    step_choices: list[StepChoiceRow]
    produces: list[str]


def _skill_option(ref: SkillRef) -> SkillOption:
    return SkillOption(
        value=f"{ref.skill}:{ref.skill_version}", label=f"{ref.skill} {ref.skill_version}"
    )


def _unavailable_reason(choices: WorkflowChoices) -> str | None:
    """None today, for every shipped workflow: no skill declares a
    minimum_model_profile above 'high', so hardware_profiles can never
    empty out in practice. Kept as a real check, not an assumption, so a
    future workflow that does reach that state is shown with a reason
    instead of an empty, unexplained select.
    """
    if not choices.hardware_profiles:
        return "No hardware profile satisfies every skill this workflow uses."
    return None


def build_offer(
    workflow: Workflow,
    choices: WorkflowChoices,
    hardware_profile_default: str,
    generative_model_default: str | None,
) -> WorkflowOffer:
    """Turn one workflow and its already-computed WorkflowChoices into what the panel shows."""
    step_choices = [
        StepChoiceRow(
            step_id=step.step_id,
            default_label=f"{step.skill} {step.skill_version}",
            options=[_skill_option(ref) for ref in step.skills],
        )
        for step in choices.steps
        if step.skills
    ]
    reason = _unavailable_reason(choices)
    return WorkflowOffer(
        name=workflow.name,
        title=workflow.title or default_title(workflow.name),
        version=workflow.version,
        description=workflow.description,
        available=reason is None,
        unavailable_reason=reason,
        hardware_profiles=choices.hardware_profiles,
        hardware_profile_default=hardware_profile_default,
        generative_models=choices.generative_models,
        generative_model_default=generative_model_default,
        step_choices=step_choices,
        produces=produces(workflow),
    )


def failed_offer(name: str, reason: str) -> WorkflowOffer:
    """The panel's answer for a workflow that never became a Workflow object at all.

    `title` falls back to `name`: nothing readable was ever parsed out of it.
    """
    return WorkflowOffer(
        name=name,
        title=name,
        version="",
        description="",
        available=False,
        unavailable_reason=reason,
        hardware_profiles=[],
        hardware_profile_default="",
        generative_models=None,
        generative_model_default=None,
        step_choices=[],
        produces=[],
    )
