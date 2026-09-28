"""Turns a workflow's step order into the one this run executes.

Split out of engine.preparation (the project's size limit) once a second
such transform was added (engine.diarize_choice.drop_declined_diarize).
Both take `ordered` and a run's RunChoices and return a new list, never
mutating the Workflow's Step objects.
"""

from __future__ import annotations

from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step


def apply_step_choices(ordered: list[Step], choices: RunChoices) -> list[Step]:
    """Replace each step the run chose a skill for with a copy naming that skill.

    A copy, because the Workflow holds the original Step and the same
    Step object may be resolved again elsewhere (engine.builtin's registry
    lookups, a second run of the same workflow), and none of those callers
    chose anything.
    """
    replaced = []
    for step in ordered:
        chosen = choices.step_skills.get(step.id)
        if chosen is None:
            replaced.append(step)
            continue
        update = {"skill": chosen.skill, "skill_version": chosen.skill_version}
        replaced.append(step.model_copy(update=update))
    return replaced
