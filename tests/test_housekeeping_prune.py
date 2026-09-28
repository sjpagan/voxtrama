"""The clean-up takes leftovers away after a week."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes.jobs import seed_job
from fakes.regenerated import seed_follow_up
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.housekeeping.prune import prune

NOW = datetime(2026, 9, 27, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _failed(session, tmp_path, day: int) -> Run:
    job = seed_job(session, tmp_path, "Retro", ["Hi."], state=RunState.FAILED)
    job.finished_at = datetime(2026, 9, day, tzinfo=UTC)
    session.get(Recording, job.recording_id).imported_at = datetime(2026, 9, day, tzinfo=UTC)
    session.commit()
    return job


def test_a_failed_job_over_a_week_old_goes_with_its_audio(session, tmp_path) -> None:
    job = _failed(session, tmp_path, day=10)

    report = prune(session, tmp_path, now=NOW)

    assert (report.jobs, report.recordings) == (1, 1)
    assert session.get(Run, job.id) is None
    assert not (tmp_path / "runs" / job.id).exists()
    assert not (tmp_path / "recordings" / job.recording_id).exists()


def test_a_failed_job_from_this_week_keeps_its_retry(session, tmp_path) -> None:
    job = _failed(session, tmp_path, day=24)

    assert prune(session, tmp_path, now=NOW).total == 0
    assert session.get(Run, job.id) is not None


def test_a_job_that_finished_well_is_never_touched(session, tmp_path) -> None:
    job = seed_job(session, tmp_path, "Retro", ["Hi."])

    assert prune(session, tmp_path, now=NOW).total == 0
    assert session.get(Recording, job.recording_id) is not None


def test_a_failed_job_keeps_the_audio_another_job_uses(session, tmp_path) -> None:
    good = seed_job(session, tmp_path, "Retro", ["Hi."])
    seed_follow_up(
        session, tmp_path, good, RunState.INTERRUPTED, finished=datetime(2026, 9, 1, tzinfo=UTC)
    )

    report = prune(session, tmp_path, now=NOW)

    assert (report.jobs, report.recordings) == (1, 0)
    assert (tmp_path / "recordings" / good.recording_id).is_dir()


def test_folders_without_a_row_go_once_untouched_for_an_hour(session, tmp_path) -> None:
    seed_job(session, tmp_path, "Kept", ["Hi."])  # a database that knows its jobs
    stale = tmp_path / "runs" / "gone-long-ago"
    fresh = tmp_path / "recordings" / "being-written"
    stale.mkdir(parents=True)
    fresh.mkdir(parents=True)
    os.utime(stale, (0, 0))

    assert prune(session, tmp_path, now=NOW).folders == 1
    assert not stale.exists()
    assert fresh.exists()


def test_an_empty_database_deletes_no_folder(session, tmp_path) -> None:
    """No rows means another database, not leftovers."""
    stale = tmp_path / "recordings" / "someone-s-audio"
    stale.mkdir(parents=True)
    os.utime(stale, (0, 0))

    assert prune(session, tmp_path, now=NOW).folders == 0
    assert stale.exists()
