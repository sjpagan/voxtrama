"""A job that finished well takes the place of the one it came from.

«Regenerate job» replaces the previous result, no versions
are kept, and only once the new job has finished well. A regeneration
that fails leaves the old result where it was, with the failed job next
to it to retry. When it succeeds, the old job is deleted and its address
leads to the new one.

Regenerate and Retry both name the job they come from in
`Run.replaces_run_id`, and that is the chain followed here, not
`reused_from_run_id`, which `voxtrama run --reuse-from` also sets without
asking for anything to be replaced. The source is
removed whatever its state. A source that had itself failed was only an
attempt, so the walk carries on to what *it* came from, and stops at the
first job that had finished well: that one is the result being replaced.
Two regenerations of the same job: the first to succeed replaces it, the
second then replaces the first, through the redirect the first one left.
A source another job still running was started from is left alone: that
job may still read it, and the clean-up (housekeeping.prune) comes later.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState, is_final
from voxtrama.db.models.run_redirect import RunRedirect
from voxtrama.housekeeping.removal import remove_run, still_needed

logger = logging.getLogger(__name__)


def _source(session: Session, run_id: str | None) -> Run | None:
    """The run `run_id` names, following the redirect of one already replaced."""
    if run_id is None:
        return None
    redirect = session.get(RunRedirect, run_id)
    return session.get(Run, redirect.target_run_id if redirect else run_id)


def retire_replaced(session: Session, runs_dir: Path, run: Run) -> list[str]:
    """Remove what `run`, just succeeded, replaces. Return the ids removed, oldest last."""
    removed: list[str] = []
    source = _source(session, run.replaces_run_id)
    while source is not None and source.id != run.id and is_final(source.state):
        if still_needed(session, source.id):
            break
        succeeded = str(source.state) == RunState.SUCCEEDED
        following = source.replaces_run_id
        if source.label and not run.label:
            run.label = source.label
        remove_run(session, runs_dir, source.id, heir=run.id)
        removed.append(source.id)
        if succeeded:
            break
        source = _source(session, following)
    if removed:
        logger.info("replaced %d earlier job(s)", len(removed))
    return removed
