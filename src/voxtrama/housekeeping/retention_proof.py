"""What proves a deletion happened: the tombstones, checked.

For every job retention emptied, the tombstone says when and under which
limit. This checks the areas the job's content lived in and lists what,
if anything, is still there: a file beside the emptied manifest, the
job's row, a transcript it produced, its recording's row or folder. A
recording another job still uses is that job's content, not a leftover.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.models.transcript import Transcript
from voxtrama.housekeeping.retention import is_tombstone
from voxtrama.manifest.writer import MANIFEST_FILENAME


@dataclass(frozen=True)
class TombstoneCheck:
    """One emptied job: when, under which limit, and what is still on disk."""

    run_id: str
    deleted_at: str
    retention_days: int
    retention_level: str
    leftovers: tuple[str, ...]


def _recording_leftovers(session: Session, recordings_dir: Path, recording_id: str) -> list[str]:
    if session.scalar(select(Run.id).where(Run.recording_id == recording_id)) is not None:
        return []  # another job's content
    found = []
    if session.get(Recording, recording_id) is not None:
        found.append(f"recording row {recording_id}")
    if (recordings_dir / recording_id).exists():
        found.append(f"recordings/{recording_id}/")
    return found


def _check(session: Session, data_dir: Path, folder: Path) -> TombstoneCheck:
    paths = get_paths(data_dir)
    manifest = json.loads((folder / MANIFEST_FILENAME).read_text())
    run_id = folder.name
    leftovers = [f"runs/{run_id}/{p.name}" for p in folder.iterdir() if p.name != MANIFEST_FILENAME]
    if session.get(Run, run_id) is not None:
        leftovers.append(f"job row {run_id}")
    produced = select(Transcript.id).where(Transcript.produced_by_run_id == run_id)
    leftovers += [f"transcript row {t}" for t in session.scalars(produced)]
    recording_id = (manifest.get("input") or {}).get("recording_id")
    if recording_id:
        leftovers += _recording_leftovers(session, paths.recordings_dir, recording_id)
    deletion = manifest["content_deleted"]
    return TombstoneCheck(
        run_id=run_id,
        deleted_at=deletion["deleted_at"],
        retention_days=deletion["retention_days"],
        retention_level=deletion["retention_level"],
        leftovers=tuple(leftovers),
    )


def check_tombstones(session: Session, data_dir: Path) -> list[TombstoneCheck]:
    """Every emptied job under runs/, oldest deletion first."""
    runs_dir = get_paths(data_dir).runs_dir
    if not runs_dir.is_dir():
        return []
    checks = [_check(session, data_dir, f) for f in runs_dir.iterdir() if is_tombstone(f)]
    return sorted(checks, key=lambda c: c.deleted_at)
