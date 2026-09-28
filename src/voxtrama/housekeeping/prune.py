"""The clean-up: what failed, stopped or was abandoned, once nobody needs it.

Without it the data directory fills up with leftovers. It
takes away:

- a job that failed, was cancelled or was interrupted, once it has been
  over for PRUNE_AFTER (a week, to press «Retry» first). A job another one
  still running was started from is kept until that one is over;
- a recording no job uses, imported more than PRUNE_AFTER ago;
- a folder under runs/ or recordings/ with no row behind it, left by a
  crash or by an older delete. Only one untouched for an hour, so a job
  being created right now is never mistaken for one.

It runs by itself (worker.prune_schedule) and from the Jobs page, and
applies retention first (housekeeping.retention). A tombstone folder
has no row behind it by design, and stays.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.housekeeping.removal import heir_of, remove_recording, remove_run, still_needed
from voxtrama.housekeeping.retention import expire, is_tombstone

PRUNE_AFTER = timedelta(days=7)
_UNTOUCHED = 3600
_LEFT_OVER = (RunState.FAILED, RunState.CANCELLED, RunState.INTERRUPTED)


@dataclass(frozen=True)
class PruneReport:
    """How much went, by kind."""

    jobs: int = 0
    recordings: int = 0
    folders: int = 0
    expired: int = 0  # Jobs whose content retention deleted

    @property
    def total(self) -> int:
        return self.jobs + self.recordings + self.folders + self.expired


def _naive(moment: datetime | None) -> datetime | None:
    return moment.replace(tzinfo=None) if moment and moment.tzinfo else moment


def _old_jobs(session: Session, cutoff: datetime) -> list[Run]:
    runs = session.scalars(select(Run).where(Run.state.in_(_LEFT_OVER)))
    return [r for r in runs if (_naive(r.finished_at or r.created_at) or cutoff) < cutoff]


def _prune_jobs(session: Session, runs_dir: Path, cutoff: datetime) -> int:
    gone = 0
    for run in _old_jobs(session, cutoff):
        if not still_needed(session, run.id):
            remove_run(session, runs_dir, run.id, heir=heir_of(session, run.id))
            gone += 1
    return gone


def _prune_recordings(session: Session, recordings_dir: Path, cutoff: datetime) -> int:
    used = select(Run.recording_id).where(Run.recording_id.is_not(None))
    unused = select(Recording).where(Recording.id.not_in(used))
    old = [r for r in session.scalars(unused) if (_naive(r.imported_at) or cutoff) < cutoff]
    for recording in old:
        remove_recording(session, recordings_dir, recording.id)
    return len(old)


def _prune_folders(root: Path, known: set[str]) -> int:
    # For security, an empty table means another database (a new
    # VOXTRAMA_DATABASE_URL, a restore gone wrong), not a folder full of
    # leftovers. Every recording would go, so nothing does.
    if not root.is_dir() or not known:
        return 0
    stale = time.time() - _UNTOUCHED
    left = [p for p in root.iterdir() if p.is_dir() and p.name not in known]
    left = [p for p in left if not is_tombstone(p)]  # The proof stays
    left = [p for p in left if p.stat().st_mtime < stale]
    for folder in left:
        shutil.rmtree(folder)
    return len(left)


def prune(
    session: Session, data_dir: Path, now: datetime | None = None, retention_days: int | None = None
) -> PruneReport:
    """Remove every leftover this module names, apply retention, say how many went."""
    expired = expire(session, data_dir, retention_days, now)
    cutoff = _naive(now or datetime.now(UTC)) - PRUNE_AFTER
    paths = get_paths(data_dir)
    jobs = _prune_jobs(session, paths.runs_dir, cutoff)
    recordings = _prune_recordings(session, paths.recordings_dir, cutoff)
    runs = set(session.scalars(select(Run.id)))
    stored = set(session.scalars(select(Recording.id)))
    folders = _prune_folders(paths.runs_dir, runs) + _prune_folders(paths.recordings_dir, stored)
    return PruneReport(jobs=jobs, recordings=recordings, folders=folders, expired=expired)
