"""A run cut off by a restart starts again by itself, from where it was.

reconcile_orphan_runs closes as `interrupted` every run whose worker went
away: `docker compose down`, the machine going to sleep or rebooting, the
worker restarting. Until now the person had to find it and press Retry.
At the worker's next start, each run just closed that way is enqueued
again exactly as api.routes.run_retry does it: same workflow, same
recording, same choices, `reused_from_run_id` pointing at it. So the steps
it had finished are adopted rather than redone (engine.reuse), and in the
step it was in, every window the model had already answered is taken from
engine.window_cache instead of being asked again. A transcription cut off
half-way is the one thing that starts over: that step is resumed whole,
not from its last chunk.

Once only. A run that was itself the automatic resume of an interrupted
run is left for the person: whatever keeps killing the worker (memory,
a crash in one step) would otherwise loop forever. A run someone stopped
is `cancelled`, not `interrupted`, and is never touched here.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState
from voxtrama.engine.catalog import load_named_workflow
from voxtrama.engine.enqueue import enqueue_run
from voxtrama.queue.base import Queue
from voxtrama.workflow.choices import RunChoices

logger = logging.getLogger(__name__)


def _already_a_resume(session: Session, run: Run) -> bool:
    if run.reused_from_run_id is None:
        return False
    source = session.get(Run, run.reused_from_run_id)
    return source is not None and source.state == RunState.INTERRUPTED


def resume_interrupted(session: Session, queue: Queue, runs: Sequence[Run]) -> int:
    """Enqueue a resume of each `interrupted` run in `runs`; how many were enqueued."""
    resumed = 0
    for run in runs:
        if run.state != RunState.INTERRUPTED or _already_a_resume(session, run):
            continue
        try:
            new_run, _ = enqueue_run(
                session,
                queue,
                run.workflow_name,
                load_named_workflow(run.workflow_name),
                recording_id=run.recording_id,
                choices=RunChoices.model_validate(run.choices) if run.choices else None,
                created_by=run.created_by,
                reused_from_run_id=run.id,
            )
        except Exception:
            logger.exception("could not resume run %s; it stays interrupted", run.id)
            continue
        logger.info("run %s was interrupted: resumed as run %s", run.id, new_run.id)
        resumed += 1
    return resumed
