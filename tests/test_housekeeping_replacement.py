"""A regenerated job that finishes well replaces the one it came from."""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.jobs import seed_job
from fakes.regenerated import seed_follow_up
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.run_redirect import RunRedirect
from voxtrama.db.models.transcript import Transcript
from voxtrama.housekeeping.replacement import retire_replaced


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'r.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def test_the_old_job_goes_and_its_address_leads_to_the_new_one(session, tmp_path) -> None:
    old = seed_job(session, tmp_path, "Retro", ["We ship on Friday."])
    new = seed_follow_up(session, tmp_path, old)

    assert retire_replaced(session, tmp_path / "runs", new) == [old.id]

    assert session.get(Run, old.id) is None
    assert not (tmp_path / "runs" / old.id).exists()
    assert session.get(RunRedirect, old.id).target_run_id == new.id
    assert new.label == "Retro"


def test_the_reused_transcript_and_the_audio_stay_with_the_new_job(session, tmp_path) -> None:
    old = seed_job(session, tmp_path, "Retro", ["We ship on Friday."])
    new = seed_follow_up(session, tmp_path, old)

    retire_replaced(session, tmp_path / "runs", new)

    transcript = session.scalar(select(Transcript))
    assert transcript.produced_by_run_id == new.id
    assert session.get(Recording, new.recording_id) is not None
    assert (tmp_path / "recordings" / new.recording_id).is_dir()


def test_a_failed_attempt_and_the_job_it_tried_to_replace_both_go(session, tmp_path) -> None:
    old = seed_job(session, tmp_path, "Retro", ["We ship on Friday."])
    failed = seed_follow_up(session, tmp_path, old, state=RunState.FAILED)
    retried = seed_follow_up(session, tmp_path, failed)

    assert retire_replaced(session, tmp_path / "runs", retried) == [failed.id, old.id]
    assert session.get(RunRedirect, old.id).target_run_id == retried.id


def test_a_job_another_one_is_still_reading_is_left_alone(session, tmp_path) -> None:
    old = seed_job(session, tmp_path, "Retro", ["We ship on Friday."])
    seed_follow_up(session, tmp_path, old, state=RunState.RUNNING)
    new = seed_follow_up(session, tmp_path, old)

    assert retire_replaced(session, tmp_path / "runs", new) == []
    assert session.get(Run, old.id) is not None


def test_a_second_regeneration_replaces_the_first_through_its_redirect(session, tmp_path) -> None:
    old = seed_job(session, tmp_path, "Retro", ["We ship on Friday."])
    first = seed_follow_up(session, tmp_path, old)
    second = seed_follow_up(session, tmp_path, old)
    retire_replaced(session, tmp_path / "runs", first)

    assert retire_replaced(session, tmp_path / "runs", second) == [first.id]
    assert session.get(RunRedirect, old.id).target_run_id == second.id


def test_a_job_started_fresh_replaces_nothing(session, tmp_path) -> None:
    job = seed_job(session, tmp_path, "Retro", ["We ship on Friday."])

    assert retire_replaced(session, tmp_path / "runs", job) == []
