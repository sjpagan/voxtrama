"""Reads a Workflow from YAML and validates it against a skill registry.

Rejects a malformed workflow before it reaches the engine:
a missing or mistyped field, an unknown skill or version, a dependency
that is missing or cyclic, and a condition that does not parse or names
a step that is not there. Every error names the field's path
(steps[2].skill), never a bare "validation error".
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.workflow.condition import STEPS_PATH, ConditionSyntaxError, parse_condition
from voxtrama.workflow.condition_state import check_state_condition, check_state_precedes
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.document import DocumentError, read_document
from voxtrama.workflow.errors import (
    CyclicDependencyError,
    SkillNotFoundError,
    UnknownStepError,
    WorkflowValidationError,
)
from voxtrama.workflow.skill import Skill

# skill name -> version -> declaration. Empty until an issue implements
# real skills. Callers build one with just the declarations a given
# workflow needs (see tests/test_workflow_loader.py).
SkillRegistry = dict[str, dict[str, Skill]]


def load_workflow(path: Path, skills: SkillRegistry) -> Workflow:
    """Parse `path` as a Workflow and validate it against `skills`."""
    try:
        workflow = read_document(path, Workflow)
    except DocumentError as exc:
        raise WorkflowValidationError(str(exc)) from exc
    validate_workflow(workflow, skills)
    return workflow


def validate_workflow(workflow: Workflow, skills: SkillRegistry) -> None:
    """Check every step's skill exists and its dependencies form a DAG."""
    _check_skills_exist(workflow, skills)
    _check_allowed_skills_exist(workflow, skills)
    _check_dependencies_exist(workflow)
    _check_no_cycles(workflow)
    _check_conditions(workflow, skills)


def _check_skills_exist(workflow: Workflow, skills: SkillRegistry) -> None:
    for index, step in enumerate(workflow.steps):
        versions = skills.get(step.skill, {})
        if step.skill_version not in versions:
            raise SkillNotFoundError(
                f"steps[{index}].skill: unknown skill '{step.skill}' version '{step.skill_version}'"
            )


def _check_allowed_skills_exist(workflow: Workflow, skills: SkillRegistry) -> None:
    """Every alternative a step's `allows.skills` names must itself resolve.

    An entry in `allows.skills` is the workflow promising a run
    that alternative is real. Left unchecked here, that promise is only
    kept or broken once a run picks it, after transcribe and
    diarize have already spent the slow half of the work: the failure the
    alternatives mechanism exists to prevent.
    """
    for index, step in enumerate(workflow.steps):
        for alt_index, alt in enumerate(step.allows.skills):
            versions = skills.get(alt.skill, {})
            if alt.skill_version not in versions:
                raise SkillNotFoundError(
                    f"steps[{index}].allows.skills[{alt_index}]: "
                    f"unknown skill '{alt.skill}' version '{alt.skill_version}'"
                )


def _check_dependencies_exist(workflow: Workflow) -> None:
    ids = {step.id for step in workflow.steps}
    for index, step in enumerate(workflow.steps):
        for dep in step.depends_on:
            if dep not in ids:
                raise UnknownStepError(f"steps[{index}].depends_on: unknown step '{dep}'")
        fallback = step.on_error.fallback_step
        if fallback is not None and fallback not in ids:
            raise UnknownStepError(
                f"steps[{index}].on_error.fallback_step: unknown step '{fallback}'"
            )


def _check_conditions(workflow: Workflow, skills: SkillRegistry) -> None:
    """Reject a malformed condition here, so it never reaches a running step.

    engine.condition parses the same string again at run time (its
    docstring says why), but a condition a person got wrong must fail
    in front of them, not halfway through a run nobody is watching.
    """
    steps_by_id = {step.id: step for step in workflow.steps}
    for index, step in enumerate(workflow.steps):
        if step.condition is None:
            continue
        try:
            condition = parse_condition(step.condition)
        except ConditionSyntaxError as exc:
            raise WorkflowValidationError(f"steps[{index}].condition: {exc}") from exc
        match = STEPS_PATH.match(condition.path)
        if match is None:
            continue
        target_id = match.group("step_id")
        if target_id not in steps_by_id:
            raise WorkflowValidationError(f"steps[{index}].condition: unknown step '{target_id}'")
        if match.group("key") == "state":
            check_state_condition(index, condition, steps_by_id[target_id], skills)
            check_state_precedes(index, target_id, step, steps_by_id)


def _check_no_cycles(workflow: Workflow) -> None:
    by_id: dict[str, Step] = {step.id: step for step in workflow.steps}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str, path: list[str]) -> None:
        if step_id in visiting:
            cycle = " -> ".join([*path, step_id])
            raise CyclicDependencyError(f"steps: dependency cycle: {cycle}")
        if step_id in visited:
            return
        visiting.add(step_id)
        for dep in by_id[step_id].depends_on:
            visit(dep, [*path, step_id])
        visiting.discard(step_id)
        visited.add(step_id)

    for step in workflow.steps:
        visit(step.id, [])
