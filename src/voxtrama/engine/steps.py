"""Turn a workflow's declared dependencies into an order of execution.

The workflow loader already refuses a cyclic workflow before the engine sees
it. This resolves the order again from the same graph and raises the same
error if it cannot: a workflow can reach the engine from somewhere that did
not validate it, and an engine that silently drops a step it cannot place
would produce a run that looks complete and is not.
"""

from __future__ import annotations

from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.errors import CyclicDependencyError, UnknownStepError


def resolve_order(workflow: Workflow) -> list[Step]:
    """Return the workflow's steps in an order that respects depends_on.

    Ties are broken by the order the steps appear in the file, so the same
    workflow always executes in the same sequence: a run that has to be
    comparable with another one cannot have its steps shuffled by
    a dictionary's iteration order.
    """
    by_id = {step.id: step for step in workflow.steps}
    _check_dependencies_exist(workflow, by_id)

    ordered: list[Step] = []
    placed: set[str] = set()

    remaining = list(workflow.steps)
    while remaining:
        ready = [step for step in remaining if all(dep in placed for dep in step.depends_on)]
        if not ready:
            unplaced = ", ".join(step.id for step in remaining)
            raise CyclicDependencyError(f"steps: dependency cycle among: {unplaced}")
        for step in ready:
            ordered.append(step)
            placed.add(step.id)
        remaining = [step for step in remaining if step.id not in placed]

    return ordered


def _check_dependencies_exist(workflow: Workflow, by_id: dict[str, Step]) -> None:
    for index, step in enumerate(workflow.steps):
        for dep in step.depends_on:
            if dep not in by_id:
                raise UnknownStepError(f"steps[{index}].depends_on: unknown step '{dep}'")
