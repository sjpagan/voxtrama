"""Which steps are someone else's fallback, and marking the ones not needed.

Split from stepping.py, which owns the run loop, so neither file grows
past the project's file-size limit.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.progress import mark_skipped
from voxtrama.workflow.definition import Step


def fallback_ids(ordered: list[Step]) -> set[str]:
    """Every step id named as some other step's fallback.

    A step in this set never runs in its own turn, only when the step it
    recovers exhausts its attempts, wherever in the order that is. Without
    this, a fallback nobody needed would still execute at its position,
    making it a second step that shares a purpose.
    """
    return {step.on_error.fallback_step for step in ordered if step.on_error.fallback_step}


def skip_unused_fallbacks(session: Session, ids: set[str], row_by_id: dict[str, RunStep]) -> None:
    """A fallback nobody needed is skipped, not pending.

    "Pending" on a finished run reads as "never reached", which is only
    true for a step the run was killed before getting to. A fallback
    whose primary step succeeded was reached in every sense that matters:
    the run considered it and decided it did not need it.
    """
    for step_id in ids:
        row = row_by_id.get(step_id)
        if row is not None and row.state == StepState.PENDING:
            mark_skipped(session, row)
