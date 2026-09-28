"""Whether a run may skip diarize, and what skipping it does to the plan.

Split out of engine.choice_check (the rejection) and engine.preparation
(the step list) into a single module because both answer "did this run
choose to skip diarize" from the same two facts: choices.diarize and
which workflow step, if any, runs the diarize skill. Kept apart, the two
could drift: preparation.py dropping the step and choice_check.py
rejecting it would each need an opinion of which step is "the diarize
step", and only one may exist.

Skipping diarize changes the *result*. It is not a performance knob: no
Segment gets a speaker and the transcript stays anonymous. A step whose
depends_on names the diarize step declares that it reads speakers
(extract_decisions in workflows/meeting-decisions.yaml does). Skipping
diarize anyway would hand that step a transcript it cannot work on,
found mid-run instead of refused up front.
"""

from __future__ import annotations

from voxtrama.engine.downloads import DIARIZE_SKILL
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.rejection import Rejection


def check_diarize_choice(choices: RunChoices, workflow: Workflow) -> list[Rejection]:
    """Reject `choices.diarize is False` when some step of `workflow` depends on it.

    Nothing to reject when the run did not ask to skip diarize, or the
    workflow has no diarize step to skip. A transcribe-only workflow
    already runs without one.
    """
    if choices.diarize is not False:
        return []
    diarize_ids = {step.id for step in workflow.steps if step.skill == DIARIZE_SKILL}
    if not diarize_ids:
        return []
    return [
        Rejection("diarize", "false", f"step {step.id}", f"depends_on {step.depends_on}")
        for step in workflow.steps
        if diarize_ids & set(step.depends_on)
    ]


def drop_declined_diarize(ordered: list[Step], choices: RunChoices) -> list[Step]:
    """Remove the diarize step from `ordered` when the run chose to skip it.

    Safe to call unconditionally: check_diarize_choice has already refused
    the request (raising ChoicesRejected, before a Run even exists) if any
    other step depends on the step this drops. By the time execution
    reaches here, nothing downstream is waiting on it.
    """
    if choices.diarize is not False:
        return ordered
    return [step for step in ordered if step.skill != DIARIZE_SKILL]
