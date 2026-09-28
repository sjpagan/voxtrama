"""Shared scaffolding for the succeeded-run result page tests.

Every test_web_run_page_result*.py file drives the same real app, inserts
the same shape of Run/RunStep/Recording/Transcript rows and writes the
same manifest.json/output.json pair. Only the assertion differs from
file to file ("divide by context"), the same reasoning
fakes/events_client.py already gives for its own split.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base, User
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.db.models.user import ROLE_OWNER
from voxtrama.manifest.output import write_run_output
from voxtrama.manifest.writer import write_run_manifest


def build_app(tmp_path: Path) -> tuple[FastAPI, Engine]:
    """A real app, wired to a file-backed database seeded with the one User
    migration 0011 requires, and `tmp_path` as its own data dir."""
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(given_name="Owner", family_name="", role=ROLE_OWNER))
        session.commit()

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    return app, engine


def _clone_step(step: RunStep) -> RunStep:
    """A second RunStep, same fields, never added to any Session. See
    insert_run's own docstring for why one of the two copies has to stay
    unbound."""
    return RunStep(
        run_id=step.run_id,
        step_id=step.step_id,
        skill=step.skill,
        skill_version=step.skill_version,
        state=step.state,
        position=step.position,
        attempts=step.attempts,
        model=step.model,
    )


def insert_run(engine: Engine, run_id: str, workflow: str, step: RunStep) -> Run:
    """A succeeded Run, its own recording_id `rec-{run_id}`, plus `step`,
    persisted as copies, never the `run`/`step` objects this returns.

    Same split test_runs_api_evidence.py's own `_run()` helper already
    makes: DB persistence and the object write_manifest_and_output reads
    back are two different needs of the same values. SQLAlchemy expires a
    committed instance's attributes on commit, and a closed Session (the
    `with` block below has already exited by the time a caller reads
    `run.id`) cannot reload them: the DetachedInstanceError this avoids.
    """
    run = Run(
        id=run_id,
        workflow_name=workflow,
        workflow_version="1.0.0",
        state=RunState.SUCCEEDED,
        recording_id=f"rec-{run_id}",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with Session(engine) as session:
        session.add(
            Run(
                id=run.id,
                workflow_name=run.workflow_name,
                workflow_version=run.workflow_version,
                state=run.state,
                recording_id=run.recording_id,
                created_at=run.created_at,
            )
        )
        session.add(_clone_step(step))
        session.commit()
    return run


def insert_recording_and_transcript(engine: Engine, run_id: str) -> None:
    """A Recording and its own one-segment Transcript, both `run_id` produced."""
    with Session(engine) as session:
        session.add(
            Recording(
                id=f"rec-{run_id}",
                original_filename="Team retro.m4a",
                stored_path="x",
                content_sha256="a" * 64,
                duration_seconds=900.0,
                media_format="wav",
            )
        )
        transcript = Transcript(
            id=f"t-{run_id}",
            recording_id=f"rec-{run_id}",
            language="en",
            model_name="whisper",
            model_revision="v1",
            hardware_profile="low",
            produced_by_run_id=run_id,
        )
        transcript.segments = [
            Segment(start=754.0, end=761.0, text="We'll ship it on 7 October.", confidence=1.0)
        ]
        session.add(transcript)
        session.commit()


def write_manifest_and_output(
    tmp_path: Path, run: Run, steps: list[RunStep], produced: dict
) -> None:
    """manifest.json and output.json for `run`, the same pair a real run leaves behind."""
    runs_dir = get_paths(tmp_path).runs_dir
    digest = write_run_output(runs_dir, run.id, produced)
    write_run_manifest(
        runs_dir,
        run,
        steps,
        None,
        {},
        None,
        None,
        evidence={},
        produced=produced,
        output_digest=digest,
    )
