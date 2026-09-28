"""Closes a RunStep left `running` by a Run that had already closed before this fix.

Split out of reconcile_close.py to stay under the project's file-length limit.
That module's `_close_running_step` is the half of this fix that runs from
now on, every time close_run closes a Run. This is the one-time catch-up for
a Run that closed before that half existed, and so never had its running
step touched. Not a migration: worker.main already runs a pass like this at
every startup for the equivalent gap one level up (a Run itself left
`running`, reconcile_orphan_runs). The same restart is where this
backfill belongs, with no new schema or new occasion to run it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState

# A Run this final on the database (db.models.run.is_final's set, repeated
# here instead of imported: that function takes a plain value, not a
# column, so there is nothing in db.models.run this can reuse directly)
# but with a RunStep still `running` predates this fix. Every Run
# reconcile_close.close_run touches from here on closes its step at the
# same time, so this only ever finds rows written before today.
_ORPHANED_STEP_RUN_STATES = (
    RunState.SUCCEEDED,
    RunState.FAILED,
    RunState.CANCELLED,
    RunState.INTERRUPTED,
)


def close_orphaned_steps(session: Session) -> int:
    """Mark `failed` every RunStep still `running` under an already-final Run.

    Same reasoning as reconcile_close._close_running_step for why `failed`
    and not a fourth StepState value, and for reusing the Run's `error` as
    the step's: this is the same close, only late. Returns how many rows
    it closed, for worker.main's startup log line.
    """
    rows = session.execute(
        select(RunStep, Run.error, Run.finished_at)
        .join(Run, Run.id == RunStep.run_id)
        .where(RunStep.state == StepState.RUNNING, Run.state.in_(_ORPHANED_STEP_RUN_STATES))
    ).all()
    for step, run_error, run_finished_at in rows:
        step.state = StepState.FAILED
        step.finished_at = run_finished_at or datetime.now(UTC)
        step.error = run_error or "closed by a run that already ended"
    if rows:
        session.commit()
    return len(rows)
