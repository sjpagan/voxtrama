"""A job started again from another one, the way Regenerate and Retry leave it."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState


def seed_follow_up(
    session: Session,
    data_dir: Path,
    source: Run,
    state: RunState = RunState.SUCCEEDED,
    finished: datetime | None = None,
) -> Run:
    """A run on `source`'s recording, started from it, with its own folder."""
    run = Run(
        workflow_name=source.workflow_name,
        workflow_version="1.0.0",
        state=state,
        recording_id=source.recording_id,
        reused_from_run_id=source.id,
        replaces_run_id=source.id,
        created_at=datetime(2026, 9, 20, tzinfo=UTC),
        finished_at=finished,
    )
    session.add(run)
    session.flush()
    (data_dir / "runs" / run.id).mkdir(parents=True)
    session.commit()
    return run
