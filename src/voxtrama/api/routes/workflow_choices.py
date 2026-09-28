"""GET /workflows/{name}/choices: what a run may pick, computed once, here.

The interface does not compute: it must not guess which
hardware profiles a workflow's skills tolerate, nor intersect the models
several steps allow, nor decide which options to offer and which to grey
out. This route does that arithmetic once and the interface only renders
the answer. Because POST /runs' own check_choices (engine.choice_check)
applies the same hardware_profile rule to reject a run, the two must
never diverge: _hardware_profiles below takes the same skill registry and
the same PROFILE_RANK ordering, so a profile this route offers is always
one check_choices would accept, and one it withholds is always one
check_choices would reject (see tests/test_workflow_choices_calc.py's
own coherence test).

generative_models says only what the workflow's steps declare in
allows.models, never what models are installed on this machine
(that reconciliation is not this route's job).

The response models this route builds (WorkflowRef, StepChoices,
WorkflowChoices) live in api.workflow_choices, not here. See that
module's own docstring for why.
"""

from __future__ import annotations

from fastapi import APIRouter

from voxtrama.api.routes.workflow_lookup import load_workflow_or_422
from voxtrama.api.workflow_choices import StepChoices, WorkflowChoices, WorkflowRef
from voxtrama.engine.builtin import BUILTIN_SKILLS
from voxtrama.engine.validation import UnknownSkillError, resolve_skill
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.skill import PROFILE_RANK

router = APIRouter()

_PROFILES_IN_ORDER = ["low", "base", "high"]


def _hardware_profiles(workflow: Workflow, skills: SkillRegistry) -> list[str]:
    """The profiles not below the highest minimum_model_profile any step's skill declares.

    Mirrors engine.choice_check._check_hardware_profile exactly, down to
    skipping a skill the registry cannot resolve: that skill already fails
    loudly elsewhere (UnknownSkillError, once a run reaches that step), and
    turning it into a narrower answer here would name the wrong cause.
    """
    highest = 0
    for step in workflow.steps:
        try:
            skill = resolve_skill(skills, step.skill, step.skill_version)
        except UnknownSkillError:
            continue
        highest = max(highest, PROFILE_RANK[skill.minimum_model_profile])
    return [profile for profile in _PROFILES_IN_ORDER if PROFILE_RANK[profile] >= highest]


def _generative_models(workflow: Workflow) -> list[str] | None:
    """The intersection of every step's allows.models, in the first declaring step's order.

    None means no step restricts this choice at all. That differs from `[]`,
    which means some step did restrict it and nothing survived every
    step's list at once. A workflow reaching that state is written badly,
    and this is where it becomes visible: it is reported, not hidden as None.
    """
    intersection: list[str] | None = None
    for step in workflow.steps:
        if not step.allows.models:
            continue
        if intersection is None:
            intersection = list(step.allows.models)
        else:
            intersection = [model for model in intersection if model in step.allows.models]
    return intersection


def _step_choices(workflow: Workflow) -> list[StepChoices]:
    """One entry per step, in declaration order: the order shown, not the order run."""
    return [
        StepChoices(
            step_id=step.id,
            skill=step.skill,
            skill_version=step.skill_version,
            skills=list(step.allows.skills),
            models=list(step.allows.models),
        )
        for step in workflow.steps
    ]


def workflow_choices_for(workflow: Workflow) -> WorkflowChoices:
    """Build the WorkflowChoices answer for an already-loaded `workflow`.

    Split out of workflow_choices_route so the workflow-choice panel a run
    starts from (which already has a Workflow object, having just loaded
    it to validate the name) can compute the same answer without a
    second HTTP round trip to itself, which the interface must not make of
    itself in the first place.
    """
    return WorkflowChoices(
        workflow=WorkflowRef(name=workflow.name, version=workflow.version),
        hardware_profiles=_hardware_profiles(workflow, BUILTIN_SKILLS),
        generative_models=_generative_models(workflow),
        steps=_step_choices(workflow),
    )


@router.get("/workflows/{name}/choices", response_model=WorkflowChoices)
def workflow_choices_route(name: str) -> WorkflowChoices:
    """What `name` lets a run choose, so the interface never has to guess."""
    return workflow_choices_for(load_workflow_or_422(name))
