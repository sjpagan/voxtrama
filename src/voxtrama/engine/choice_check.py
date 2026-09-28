"""Checks a run's chosen options against what a skill or a workflow allows.

The rule that the tighter constraint wins extends to this third level
without exception: a run choice that widens a constraint declared by a
skill or a workflow step is rejected outright, never applied with a
warning. Nothing calls check_choices yet: the route and the engine
that will submit a RunChoices for checking are the next issue. This
module only answers the question they will ask (would `choices` be
accepted?), so that answer exists before anything depends on it.

Rejection and ChoicesRejected live in workflow.rejection. That module's
docstring explains why the shape and the rules that produce it are split
across the workflow/engine boundary.
"""

from __future__ import annotations

from voxtrama.engine.diarize_choice import check_diarize_choice
from voxtrama.engine.provider_choice import check_provider_choice
from voxtrama.engine.resource_choice import check_resource_choice
from voxtrama.engine.validation import UnknownSkillError, resolve_skill
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import SkillRef, Step, Workflow
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.rejection import ChoicesRejected, Rejection
from voxtrama.workflow.skill import PROFILE_RANK


def check_choices(choices: RunChoices, workflow: Workflow, skills: SkillRegistry) -> None:
    """Raise ChoicesRejected if `choices` widens a constraint the workflow or a skill declares.

    Raises nothing when `choices` is empty: a run that chose nothing
    cannot contradict anything. Every rejection is collected before
    raising, in a fixed order: workflow step order for the first two
    checks, sorted step_skills keys for the third, workflow step order
    again for the fourth (the diarize dependency), cores_per_chunk
    before parallel_chunks for the fifth, the provider last. Two
    identical requests always produce the same message.
    """
    rejections = [
        *_check_hardware_profile(choices, workflow, skills),
        *_check_generative_model(choices, workflow),
        *_check_step_skills(choices, workflow),
        *check_diarize_choice(choices, workflow),
        *check_resource_choice(choices),
        *check_provider_choice(choices, workflow, skills),
    ]
    if rejections:
        raise ChoicesRejected(rejections)


def _check_hardware_profile(
    choices: RunChoices, workflow: Workflow, skills: SkillRegistry
) -> list[Rejection]:
    if choices.hardware_profile is None:
        return []
    chosen_rank = PROFILE_RANK[choices.hardware_profile]
    rejections: list[Rejection] = []
    for step in workflow.steps:
        try:
            skill = resolve_skill(skills, step.skill, step.skill_version)
        except UnknownSkillError:
            # An unresolved skill already fails loudly elsewhere
            # (UnknownSkillError, once the run reaches that step): turning
            # it into a choice rejection here would name the wrong cause.
            continue
        if chosen_rank >= PROFILE_RANK[skill.minimum_model_profile]:
            continue
        declared_by = f"skill {skill.name}@{skill.version}"
        constraint = f"minimum_model_profile '{skill.minimum_model_profile}'"
        rejections.append(
            Rejection("hardware_profile", choices.hardware_profile, declared_by, constraint)
        )
    return rejections


def _check_generative_model(choices: RunChoices, workflow: Workflow) -> list[Rejection]:
    if choices.generative_model is None:
        return []
    rejections: list[Rejection] = []
    for step in workflow.steps:
        # A step that declares no models does not restrict this choice at
        # all: an undeclared constraint is not a constraint.
        if not step.allows.models or choices.generative_model in step.allows.models:
            continue
        declared_by = f"step {step.id}"
        constraint = f"allows.models {step.allows.models}"
        rejections.append(
            Rejection("generative_model", choices.generative_model, declared_by, constraint)
        )
    return rejections


def _check_step_skills(choices: RunChoices, workflow: Workflow) -> list[Rejection]:
    steps_by_id = {step.id: step for step in workflow.steps}
    rejections: list[Rejection] = []
    for step_id in sorted(choices.step_skills):
        chosen = choices.step_skills[step_id]
        declared_by, constraint = _step_skill_reason(workflow, steps_by_id.get(step_id), chosen)
        if constraint is None:
            continue
        field = f"step_skills[{step_id}]"
        value = f"{chosen.skill}@{chosen.skill_version}"
        rejections.append(Rejection(field, value, declared_by, constraint))
    return rejections


def _step_skill_reason(
    workflow: Workflow, step: Step | None, chosen: SkillRef
) -> tuple[str, str | None]:
    """Who rejects `chosen` for `step`, and why, or (*, None) if it is allowed.

    A single place for the three distinct reasons the module docstring
    promises stay distinguishable: "no such step", "this step offers no
    choice", and "not among the offered ones" must never read the same.
    """
    if step is None:
        return f"workflow {workflow.name}@{workflow.version}", "no step with that id"
    if not step.allows.skills:
        return f"step {step.id}", "no skill alternatives"
    if chosen not in step.allows.skills:
        alternatives = ", ".join(f"{alt.skill}@{alt.skill_version}" for alt in step.allows.skills)
        return f"step {step.id}", f"allows.skills [{alternatives}]"
    return f"step {step.id}", None
