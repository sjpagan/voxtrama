"""Executes a Run's workflow, step by step, to a final state.

No HTTP and no queue involved: the CLI and the API both reach it through the
queue, and it knows about neither. Creating a Run lives in engine.enqueue,
the one place a Run is created and handed to the queue, so this
module only executes one that already exists. execute_run takes its steps
from the workflow the Run names, not from a caller-supplied iterable: the
previous signature was orchestration with nothing to orchestrate.

Resolving the workflow and running a single step live in engine.preparation,
and closing a Run that failed lives in engine.failure. Both are split out so
this file stays under the project's size limit.

Every state change here is committed, not flushed: a reader on another
connection (the API, the web interface, a database client)
would otherwise see `pending` for a run's entire length. The CLI never
noticed, because it reads the progress file instead.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.failure import fail_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.engine.progress_file import publish_run_state
from voxtrama.engine.step_loop import run_steps
from voxtrama.engine.stepping import SteppingTarget, publish_manifest
from voxtrama.engine.validation import error_code_for
from voxtrama.housekeeping.replacement import retire_replaced
from voxtrama.workflow.definition import Step, Workflow

logger = logging.getLogger(__name__)


def execute_run(session: Session, run_id: str, workflow: Workflow | None = None) -> Run:
    """Load a pending Run, execute its workflow's steps in order, record the outcome.

    `workflow` is an injection point for tests, which need a workflow that
    exists only in memory. Left out, the run's workflow name is resolved
    through the catalogue.
    """
    run = session.get(Run, run_id)
    if run is None:
        raise ValueError(f"Run not found: {run_id}")

    run.state = RunState.RUNNING
    run.started_at = datetime.now(UTC)
    # Committed, not flushed: see the note on visibility below.
    session.commit()
    logger.info("run started")
    runs_dir = get_paths(get_settings().data_dir).runs_dir
    publish_run_state(runs_dir, run, message="preparing")

    try:
        ordered, rows, context, definition = prepare_run(session, run, workflow)
    except Exception as exc:
        # Nothing ran yet. error_code_for also names ChoicesRejected.
        return fail_run(session, run, exc, code=error_code_for(exc))

    try:
        return _run_planned_steps(session, run, runs_dir, ordered, rows, context, definition)
    except Exception as exc:
        # This far out nothing names a step to blame, so error_step stays
        # None. Not BaseException: KeyboardInterrupt/SystemExit
        # is someone asking the run to stop, not the work failing, and
        # reporting it "failed" would hide that.
        return fail_run(
            session,
            run,
            exc,
            code=error_code_for(exc),
            rows=rows,
            workflow=definition,
            context=context,
        )


def _run_planned_steps(
    session: Session,
    run: Run,
    runs_dir: Path,
    ordered: list[Step],
    rows: list[RunStep],
    context: ExecutionContext,
    definition: Workflow,
) -> Run:
    """Run an already-planned Run's steps to a final state, manifest included."""
    target = SteppingTarget(runs_dir, run, context, rows, definition, BUILTIN_SKILLS)
    # From here the manifest exists, before any step has run.
    publish_manifest(target)

    failure = run_steps(target, ordered, _execute_step)
    if failure is not None:
        return fail_run(
            session,
            run,
            failure.exc,
            code=error_code_for(failure.exc),
            step=failure.step_id,
            rows=rows,
            workflow=definition,
            context=context,
        )

    run.state = RunState.SUCCEEDED
    run.finished_at = datetime.now(UTC)
    logger.info("run finished")
    session.commit()
    publish_run_state(runs_dir, run, step_total=len(ordered), message="done")
    publish_manifest(target)
    try:  # Never turns a run that succeeded into one that failed
        retire_replaced(session, runs_dir, run)
    except Exception:
        logger.exception("could not remove the job this one replaces")
    return run


def _execute_step(context: ExecutionContext, step: Step, row: RunStep) -> None:
    execute_step(context, step, row, BUILTIN_STEPS, BUILTIN_SKILLS)
