"""Loader-time checks for steps.<id>.state conditions.

Split out of workflow.loader to keep that file under the file-length limit.
The literal, the operator and the output_schema collision are three checks
about the same narrow question (does this condition on a step's state mean
something real?) and belong together, apart from the general shape checks
loader.py runs for every condition regardless of what path it names.
"""

from __future__ import annotations

from voxtrama.workflow.condition import STEP_STATE_OPERATORS, STEP_STATE_VALUES, Condition
from voxtrama.workflow.definition import Step
from voxtrama.workflow.errors import WorkflowValidationError
from voxtrama.workflow.skill import Skill


def check_state_condition(
    index: int, condition: Condition, target: Step, skills: dict[str, dict[str, Skill]]
) -> None:
    """steps.<id>.state has its own literals, operators, and a collision to rule out.

    A workflow that will never branch as written should say so at load
    time, not stay silent until a run reaches it.
    """
    if condition.operator not in STEP_STATE_OPERATORS:
        raise WorkflowValidationError(
            f"steps[{index}].condition: operator '{condition.operator}' is not valid on a "
            f"step's state; use one of {sorted(STEP_STATE_OPERATORS)}"
        )
    if condition.literal not in STEP_STATE_VALUES:
        raise WorkflowValidationError(
            f"steps[{index}].condition: '{condition.literal}' is not a state a step can "
            f"reach; use one of {sorted(STEP_STATE_VALUES)}"
        )
    skill = skills.get(target.skill, {}).get(target.skill_version)
    if skill is not None and "state" in skill.output_schema.get("properties", {}):
        raise WorkflowValidationError(
            f"steps[{index}].condition: 'state' means the state of step '{target.id}' here, "
            f"but its skill '{target.skill}' declares a 'state' property in output_schema"
        )


def check_state_precedes(
    index: int, target_id: str, step: Step, steps_by_id: dict[str, Step]
) -> None:
    """steps.<target_id>.state only means something if `step` runs after it.

    engine.steps.resolve_order orders purely on depends_on and never looks
    at condition, so without a depends_on edge to target_id (direct or
    through another step) nothing guarantees target_id has already run
    when this step's condition is evaluated. Reading state on a step that
    has not run yet is what engine.condition raises
    ConditionEvaluationError for, and today nothing catches that: the run
    is left stuck `running` instead of failing with a message. Closing it
    here turns that into a typo caught before anything runs.
    """
    if not _depends_on_transitively(step, target_id, steps_by_id):
        raise WorkflowValidationError(
            f"steps[{index}].condition: reads steps.{target_id}.state, but this step does not "
            f"depend on '{target_id}'; add it to depends_on so it is guaranteed to run first"
        )


def _depends_on_transitively(step: Step, target_id: str, steps_by_id: dict[str, Step]) -> bool:
    """Whether `target_id` is one of `step`'s dependencies, directly or through another one."""
    seen: set[str] = set()
    frontier = list(step.depends_on)
    while frontier:
        dep_id = frontier.pop()
        if dep_id == target_id:
            return True
        if dep_id in seen:
            continue
        seen.add(dep_id)
        dep_step = steps_by_id.get(dep_id)
        if dep_step is not None:
            frontier.extend(dep_step.depends_on)
    return False
