"""Closes a Run that did not make it, and writes what it managed before it failed.

Split from run.py, which owns the happy path, so neither file grows past
the project's file-size limit. A failed run's manifest is the most
important one: it is the only place that records how far
the run got, so it is written here even when nothing was ever planned.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.run import Run, RunState, is_final
from voxtrama.db.models.step import RunStep
from voxtrama.engine.builtin import BUILTIN_SKILLS
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.progress_file import publish_run_state
from voxtrama.manifest.output import write_run_output
from voxtrama.manifest.writer import write_run_manifest
from voxtrama.workflow.definition import Workflow

logger = logging.getLogger(__name__)


def fail_run(
    session: Session,
    run: Run,
    exc: Exception,
    *,
    code: str = "internal",
    step: str | None = None,
    rows: list[RunStep] | None = None,
    workflow: Workflow | None = None,
    context: ExecutionContext | None = None,
) -> Run:
    if is_final(run.state):
        # A run that already settled (succeeded or failed) must not be
        # reopened by a later fault. The manifest write at the end of a
        # successful run raising is that case, and the same guard
        # protects every other caller of fail_run. The fault still goes to
        # the log, but it does not overwrite a result already declared.
        logger.warning("fail_run called on a run already in a final state (%s)", run.state)
        return run
    run.state = RunState.FAILED
    run.error = str(exc)
    run.error_code = code
    run.error_step = step
    run.finished_at = datetime.now(UTC)
    logger.error("run failed")
    session.commit()
    runs_dir = get_paths(get_settings().data_dir).runs_dir
    publish_run_state(runs_dir, run, message=str(exc))
    recording = context.recording if context is not None else None
    transcript = context.transcript if context is not None else None
    evidence = context.evidence if context is not None else None
    produced = context.produced if context is not None else {}
    # output.json first, manifest second, for the same reason as
    # engine.stepping.publish_manifest.
    digest = write_run_output(runs_dir, run.id, produced)
    write_run_manifest(
        runs_dir,
        run,
        rows or [],
        workflow,
        BUILTIN_SKILLS,
        recording,
        transcript,
        evidence,
        produced,
        output_digest=digest,
    )
    return run
