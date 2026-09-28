"""Where `local_only` comes from for a step: its skill, its workflow, itself.

A workflow can declare `privacy: local_only` for all its
steps, and a single step can declare it for itself. Both only narrow: a
workflow or a step can keep a skill that says `any` on the machine, never
let out a skill that declared itself `local_only` (the tighter
constraint wins). A step or a workflow that says
`any` adds nothing.
"""

from __future__ import annotations

from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.skill import Privacy


def declared_local_only(workflow: Workflow, step: Step) -> str | None:
    """Who, above the skill, keeps `step` local: "step <id>", "workflow <name>", or None."""
    if step.privacy == Privacy.LOCAL_ONLY:
        return f"step {step.id}"
    if workflow.privacy == Privacy.LOCAL_ONLY:
        return f"workflow {workflow.name}"
    return None


def local_only_steps(workflow: Workflow, skills: SkillRegistry) -> list[str]:
    """Every step that runs under `local_only`, whoever declared it."""
    kept = []
    for step in workflow.steps:
        skill = skills.get(step.skill, {}).get(step.skill_version)
        own = skill is not None and skill.privacy == Privacy.LOCAL_ONLY
        if own or declared_local_only(workflow, step):
            kept.append(step.id)
    return kept


def kept_local(workflow: Workflow) -> dict[str, str]:
    """Step id -> who declared it `local_only` above its skill, for every such step."""
    declared = {step.id: declared_local_only(workflow, step) for step in workflow.steps}
    return {step_id: by for step_id, by in declared.items() if by}
