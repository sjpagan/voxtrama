"""The run's provider choice, checked before the run starts.

A run names one of the configured providers (providers.registry); a name
nobody configured is rejected. A run that names a remote provider on a
workflow with a generative `local_only` skill is rejected too, before it
starts, even when that skill sits in a step this run would not execute. A
constraint that depends on a condition is not a constraint. The same holds
for a step its workflow or itself keeps local, and for the installation's
default provider when the run names none. Extractive skills (transcribe,
diarize) never call a text provider, so their `local_only` has no bearing
on this choice.
"""

from __future__ import annotations

from voxtrama.config.settings import get_settings
from voxtrama.engine.validation import UnknownSkillError, resolve_skill
from voxtrama.providers.registry import LOCAL, configured_providers, provider_named
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.privacy import declared_local_only
from voxtrama.workflow.rejection import Rejection
from voxtrama.workflow.skill import ModelClass, Privacy, Skill

FIELD = "provider"


def _steps_of(choices: RunChoices, workflow: Workflow) -> list[tuple[Step, str, str]]:
    """Every step with the skill it will run, the run's skill choice applied."""
    steps = []
    for step in workflow.steps:
        ref = choices.step_skills.get(step.id)
        name, version = (ref.skill, ref.skill_version) if ref else (step.skill, step.skill_version)
        steps.append((step, name, version))
    return steps


def _kept_local_by(workflow: Workflow, step: Step, skill: Skill) -> str | None:
    """Who keeps a generative step on the machine: its skill, its workflow or itself."""
    if skill.model_class != ModelClass.GENERATIVE:
        return None  # never calls a text provider
    if skill.privacy == Privacy.LOCAL_ONLY:
        return f"skill {skill.name}@{skill.version} (step {step.id})"
    return declared_local_only(workflow, step)


def check_provider_choice(
    choices: RunChoices, workflow: Workflow, skills: SkillRegistry
) -> list[Rejection]:
    """Why the run's provider cannot serve this workflow. Empty when it can.

    The run's choice, or the installation's default when it chose none:
    a workflow kept local refuses a remote default as well.
    """
    providers = configured_providers(get_settings())
    provider = provider_named(get_settings(), choices.provider)
    if choices.provider is not None and choices.provider not in providers:
        return [Rejection(FIELD, choices.provider, "installation", "not a configured provider")]
    if provider is None or provider.locality == LOCAL:
        return []
    rejections = []
    for step, name, version in _steps_of(choices, workflow):
        try:
            skill = resolve_skill(skills, name, version)
        except UnknownSkillError:
            continue  # fails loudly elsewhere, under its own name
        declared_by = _kept_local_by(workflow, step, skill)
        if declared_by:
            rejections.append(Rejection(FIELD, provider.name, declared_by, "privacy local_only"))
    return rejections
