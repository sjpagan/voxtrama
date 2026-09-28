"""Retention deletes a finished job's content and leaves its tombstone."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes.jobs import seed_job
from fakes.manifest import manifest_dict
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Transcript
from voxtrama.housekeeping.prune import prune
from voxtrama.housekeeping.retention import expire
from voxtrama.housekeeping.retention_proof import check_tombstones
from voxtrama.manifest.schema import Manifest

NOW = datetime(2026, 9, 27, tzinfo=UTC)


@pytest.fixture
def session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'r.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _finished(session, tmp_path, day: int, month: int = 8, job_days: int | None = None) -> Run:
    job = seed_job(session, tmp_path, "Retro", ["Giulia said yes."])
    job.finished_at = datetime(2026, month, day, tzinfo=UTC)
    job.choices = {"retention_days": job_days} if job_days else None
    manifest = manifest_dict()
    manifest["run"]["id"] = job.id
    manifest["run"]["label"] = "Retro with Giulia"
    manifest["input"]["recording_id"] = job.recording_id
    manifest["choices"]["context"] = "People: Giulia"
    (tmp_path / "runs" / job.id / "manifest.json").write_text(json.dumps(manifest))
    session.commit()
    return job


def test_nothing_is_deleted_while_no_level_sets_a_limit(session, tmp_path) -> None:
    job = _finished(session, tmp_path, day=1, month=1)

    assert expire(session, tmp_path, None, NOW) == 0
    assert session.get(Run, job.id) is not None


def test_past_the_installation_limit_the_whole_job_goes(session, tmp_path) -> None:
    job = _finished(session, tmp_path, day=1)

    assert expire(session, tmp_path, 30, NOW) == 1

    folder = tmp_path / "runs" / job.id
    assert [p.name for p in folder.iterdir()] == ["manifest.json"]
    assert session.get(Run, job.id) is None
    assert session.get(Recording, job.recording_id) is None
    assert not (tmp_path / "recordings" / job.recording_id).exists()
    assert session.scalars(select(Transcript)).first() is None


def test_the_tombstone_is_an_emptied_manifest_that_says_when_and_why(session, tmp_path) -> None:
    job = _finished(session, tmp_path, day=1)

    expire(session, tmp_path, 30, NOW)

    tomb = json.loads((tmp_path / "runs" / job.id / "manifest.json").read_text())
    manifest = Manifest.model_validate(tomb)  # a reader of manifests reads it
    assert manifest.content_deleted.retention_days == 30
    assert manifest.content_deleted.retention_level == "installation"
    assert manifest.content_deleted.deleted_at.startswith("2026-09-27")
    assert manifest.run.label is None and manifest.choices.context is None
    assert manifest.outputs == [] and manifest.input.sha256 == "a" * 64
    assert "Giulia" not in json.dumps(tomb)


def test_a_job_can_shorten_the_limit_but_not_lengthen_it(session, tmp_path) -> None:
    short = _finished(session, tmp_path, day=15, month=9, job_days=7)
    long = _finished(session, tmp_path, day=15, month=9, job_days=90)

    assert expire(session, tmp_path, 10, NOW) == 2

    levels = {c.run_id: c.retention_level for c in check_tombstones(session, tmp_path)}
    assert levels == {short.id: "job", long.id: "installation"}


def test_a_job_within_its_limit_or_still_running_stays(session, tmp_path) -> None:
    recent = _finished(session, tmp_path, day=20, month=9)
    running = _finished(session, tmp_path, day=1, month=1)
    running.state = RunState.RUNNING
    session.commit()

    assert expire(session, tmp_path, 30, NOW) == 0
    assert session.get(Run, recent.id) and session.get(Run, running.id)


def test_the_clean_up_keeps_the_tombstone_and_the_proof_finds_nothing_left(
    session, tmp_path
) -> None:
    job = _finished(session, tmp_path, day=1)

    report = prune(session, tmp_path, now=NOW, retention_days=30)

    assert report.expired == 1
    assert (tmp_path / "runs" / job.id / "manifest.json").is_file()
    [check] = check_tombstones(session, tmp_path)
    assert check.run_id == job.id and check.leftovers == ()


def test_the_proof_names_what_is_still_on_disk(session, tmp_path) -> None:
    job = _finished(session, tmp_path, day=1)
    expire(session, tmp_path, 30, NOW)
    (tmp_path / "runs" / job.id / "output.json").write_text("{}")

    [check] = check_tombstones(session, tmp_path)

    assert check.leftovers == (f"runs/{job.id}/output.json",)
