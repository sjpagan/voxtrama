"""`voxtrama retention` proves what retention deleted."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fakes.jobs import seed_job
from fakes.manifest import manifest_dict
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from voxtrama.cli.main import app
from voxtrama.config.settings import get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.housekeeping import retention
from voxtrama.housekeeping.retention import expire, retention_of
from voxtrama.manifest.jsonfile import write_atomic

NOW = datetime(2026, 9, 27, tzinfo=UTC)


@pytest.fixture
def session(tmp_path, monkeypatch):
    db = tmp_path / "voxtrama.db"
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db}")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    get_settings.cache_clear()


def _job(session, tmp_path, skill: str = "summarize"):
    job = seed_job(session, tmp_path, "Retro", ["Hi."])
    job.finished_at = datetime(2026, 9, 1, tzinfo=UTC)
    session.add(
        RunStep(
            run_id=job.id,
            step_id=skill,
            skill=skill,
            skill_version="1.0.0",
            position=0,
            state=StepState.SUCCEEDED,
        )
    )
    manifest = manifest_dict()
    manifest["input"]["recording_id"] = job.recording_id
    write_atomic(manifest, tmp_path / "runs" / job.id / "manifest.json")
    session.commit()
    return job


def test_a_workflow_s_skill_can_shorten_the_limit(session, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        retention, "_policy", lambda s: "7d" if s == "summarize" else "follows_recording"
    )
    job = _job(session, tmp_path)

    rule = retention_of(session, job, 30)

    assert (rule.days, rule.level) == (7, "workflow")
    assert expire(session, tmp_path, None, NOW) == 1


def test_the_command_lists_the_deleted_jobs_and_what_is_left(session, tmp_path) -> None:
    job = _job(session, tmp_path, skill="transcribe")
    expire(session, tmp_path, 7, NOW)

    clean = CliRunner().invoke(app, ["retention"])
    (tmp_path / "runs" / job.id / "stray.txt").write_text("x")
    dirty = CliRunner().invoke(app, ["retention"])

    assert clean.exit_code == 0, clean.output
    assert f"{job.id}  deleted 2026-09-27" in clean.output and "nothing left" in clean.output
    assert dirty.exit_code == 1 and f"runs/{job.id}/stray.txt" in dirty.output
