"""Writes a Run's closing state to the database and to disk.

Split out of reconcile.py, which owns *deciding* whether and how a
`running` Run should close. This owns *doing* it, exactly once. Two
places want a `running` Run closed as `cancelled`: engine.reconcile
finding one whose queue job it now reports `cancelled`, and
api.routes.run_cancel finding one whose job the queue no longer has any
record of (JobNotFound) while trying to cancel it directly.
Both face the same fact on disk: a manifest and a progress file that
execute_run already wrote, still claiming `running` unless someone
rewrites them. More than once, when two places solved that problem
differently, one of them forgot `cancelled`. So there is one function.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.builtin import BUILTIN_SKILLS
from voxtrama.engine.progress_file import publish_run_state
from voxtrama.engine.reconcile_manifest import (
    existing_output_digest,
    existing_produced,
    recording_and_transcript,
    reloaded_workflow,
)
from voxtrama.manifest.writer import write_run_manifest

logger = logging.getLogger(__name__)

# Run.error_code's closed set (see Run.error_code's docstring), not a code
# from the API error table. That table maps *response* codes, and neither
# "interrupted" nor "cancelled" is ever one: output_schema_violation and
# evidence_not_anchored already live in this same set without appearing
# there either.
INTERRUPTED_ERROR_CODE = "interrupted"
_INTERRUPTED_MESSAGE = "the worker executing this run is no longer running"

# Public, unlike _INTERRUPTED_MESSAGE above: api.routes.run_cancel imports
# both, because it is the other caller of close_run below, and the two
# must not disagree about what a cancelled Run says.
CANCELLED_ERROR_CODE = "cancelled"
CANCELLED_MESSAGE = "cancelled on request"


def close_run(session: Session, runs_dir: Path, run: Run, target_state: RunState) -> None:
    """Mark `run` in `target_state`, and rewrite its progress file and manifest.

    `workflow_from_run=False`: this function never runs anything, it only
    closes a Run something else left `running`. reloaded_workflow's
    definition can be the run's own copy, already on disk, or a fallback
    read from the catalogue just now, and this caller cannot tell
    which. Only the first would be true to attest, and this function has
    no grounds to attest either.
    """
    cancelled = target_state == RunState.CANCELLED
    message = CANCELLED_MESSAGE if cancelled else _INTERRUPTED_MESSAGE
    run.state = target_state
    run.finished_at = datetime.now(UTC)
    run.error_code = CANCELLED_ERROR_CODE if cancelled else INTERRUPTED_ERROR_CODE
    run.error = message
    logger.warning("run closed as %s: %s", target_state.value, message)
    _close_running_step(session, run.id, message, run.finished_at)
    session.commit()
    publish_run_state(runs_dir, run, message=message)
    rows = session.scalars(select(RunStep).where(RunStep.run_id == run.id)).all()
    recording, transcript = recording_and_transcript(session, run)
    write_run_manifest(
        runs_dir,
        run,
        list(rows),
        reloaded_workflow(runs_dir, run.id, run.workflow_name),
        BUILTIN_SKILLS,
        recording,
        transcript,
        produced=existing_produced(runs_dir, run.id),
        output_digest=existing_output_digest(runs_dir, run.id),
        workflow_from_run=False,
    )


def _close_running_step(session: Session, run_id: str, message: str, finished_at: datetime) -> None:
    """The one RunStep still `running` when `run` closes does not stay so forever.

    `engine.step_loop` runs one step at a time, so at most one row is ever
    `running` here, never a chain to walk. `failed`, not a fourth
    StepState: that enum (db.models.step) is not this change's to extend.
    `failed` already means "did not reach a successful conclusion" in this
    same shape (engine.progress's `row.state = StepState.FAILED;
    row.error = str(exc)` on a genuine skill exception), and `error`
    carries which of the two closes this was, the same `message`
    `run.error` just got, so a manifest or this page never disagrees with
    itself about why. A `pending` row is deliberately left alone: unlike
    this one it never started, which is what it already shows. This is
    run_cancel._close_never_started's reasoning, one level up, for the run
    as a whole.
    """
    step = session.scalars(
        select(RunStep).where(RunStep.run_id == run_id, RunStep.state == StepState.RUNNING)
    ).first()
    if step is not None:
        step.state = StepState.FAILED
        step.finished_at = finished_at
        step.error = message
