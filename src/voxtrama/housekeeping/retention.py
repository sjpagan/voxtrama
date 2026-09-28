"""Retention: a finished job past its limit loses its content.

The unit is the whole job: audio, transcript, recap and every file it
produced go together. The limit is the strictest of the installation's,
the workflow's and the job's own (workflow.retention). An installation
starts with none. What remains is the tombstone (manifest.deletion): the
folder keeps only its emptied manifest.json, which says when and under
which limit. The check runs when the application starts, not from a
process that wakes at midnight: worker.prune_schedule runs it at
start-up, with the clean-up, and the Jobs page's button runs it too.

The deletion is real: files removed from disk, rows removed from the
database. A recording another job still uses stays, since it is that
job's content too. So does a transcript another job reused (removal).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.db.models.run import Run, is_final
from voxtrama.db.models.step import RunStep
from voxtrama.housekeeping.removal import (
    contained,
    heir_of,
    remove_recording,
    remove_run,
    still_needed,
)
from voxtrama.manifest.deletion import ManifestDeletion, emptied
from voxtrama.manifest.jsonfile import write_atomic
from voxtrama.manifest.writer import MANIFEST_FILENAME
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.retention import FOLLOWS_RECORDING, Retention, strictest, workflow_days


def _policy(skill: str) -> str:
    """The skill's declared retention_policy. A built-in one declares none."""
    from voxtrama.engine.skill_catalog import load_named_skill_file

    try:
        return load_named_skill_file(skill).skill.retention_policy
    except Exception:  # a built-in, or a file gone or broken: no limit of its own
        return FOLLOWS_RECORDING


def retention_of(session: Session, run: Run, installation_days: int | None) -> Retention | None:
    """The limit `run` lives under, None when no level sets one."""
    skills = set(session.scalars(select(RunStep.skill).where(RunStep.run_id == run.id)))
    job = RunChoices.model_validate(run.choices or {}).retention_days
    return strictest(installation_days, workflow_days([_policy(s) for s in skills]), job)


def is_tombstone(folder: Path) -> bool:
    """Whether `folder` is what a job left after retention deleted its content."""
    try:
        manifest = json.loads((folder / MANIFEST_FILENAME).read_text())
    except (OSError, ValueError):
        return False
    return isinstance(manifest, dict) and bool(manifest.get("content_deleted"))


def _bury(runs_dir: Path, run_id: str, manifest: dict | None, deletion: ManifestDeletion) -> None:
    folder = contained(runs_dir, run_id)
    if folder is not None and manifest is not None:
        write_atomic(emptied(manifest, deletion), folder / MANIFEST_FILENAME)


def _read_manifest(runs_dir: Path, run_id: str) -> dict | None:
    folder = contained(runs_dir, run_id)
    try:
        return json.loads((folder / MANIFEST_FILENAME).read_text()) if folder else None
    except (OSError, ValueError):
        return None


def delete_content(
    session: Session, data_dir: Path, run: Run, rule: Retention, now: datetime
) -> None:
    """Delete everything `run` holds and leave its tombstone."""
    paths = get_paths(data_dir)
    run_id, recording_id = run.id, run.recording_id
    manifest = _read_manifest(paths.runs_dir, run_id)
    remove_run(session, paths.runs_dir, run_id, heir=heir_of(session, run_id))
    if (
        recording_id
        and session.scalar(select(Run.id).where(Run.recording_id == recording_id)) is None
    ):
        remove_recording(session, paths.recordings_dir, recording_id)
    deletion = ManifestDeletion(
        deleted_at=now.isoformat(), retention_days=rule.days, retention_level=rule.level
    )
    _bury(paths.runs_dir, run_id, manifest, deletion)


def ended(run: Run) -> datetime:
    """When `run` finished, aware, or its creation when it never started."""
    moment = run.finished_at or run.created_at
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def expire(
    session: Session, data_dir: Path, installation_days: int | None, now: datetime | None = None
) -> int:
    """Delete the content of every finished job past its limit. Return how many went."""
    now = now or datetime.now(UTC)
    gone = 0
    for run in list(session.scalars(select(Run))):
        if not is_final(run.state) or still_needed(session, run.id):
            continue
        rule = retention_of(session, run, installation_days)
        if rule is not None and ended(run) + timedelta(days=rule.days) <= now:
            delete_content(session, data_dir, run, rule, now)
            gone += 1
    return gone
