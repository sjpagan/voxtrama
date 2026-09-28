"""A regenerated job that reused its steps still shows what it reused.

Found in the alpha test: regenerating with nothing changed gave
a job whose Transcript tab read "No transcript yet", because the view
only knew the transcript a job wrote itself, and whose steps read
"< 1 min" as if they had run.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.jobs import seed_job
from fakes.queue import InMemoryQueue
from fakes.regenerated import seed_follow_up
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from test_run_regenerate import _client as regenerate_client
from test_run_regenerate import _new_run as new_run

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.run import RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.db.models.transcript import Transcript
from voxtrama.housekeeping.removal import remove_run

STEPS = ("transcribe", "diarize")


@pytest.fixture
def engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    yield engine
    engine.dispose()


def _regenerated(session: Session, tmp_path: Path) -> tuple[str, str]:
    """(source id, regenerated id): every step of the second adopted from the first."""
    source = seed_job(session, tmp_path, "Retro", ["We ship on Friday."])
    new = seed_follow_up(session, tmp_path, source)
    transcript_id = session.scalar(select(Transcript.id))
    for position, step_id in enumerate(STEPS):
        session.add(
            RunStep(
                run_id=new.id,
                step_id=step_id,
                skill=step_id,
                skill_version="1.0.0",
                state=StepState.SUCCEEDED,
                position=position,
                reused_from_run_id=source.id,
            )
        )
    session.commit()
    output = {"run_id": new.id, "steps": {"transcribe": {"transcript_id": transcript_id}}}
    (tmp_path / "runs" / new.id / "output.json").write_text(json.dumps(output))
    return source.id, new.id


def _client(engine, tmp_path: Path) -> TestClient:
    def _get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    return TestClient(app)


def test_the_view_shows_the_transcript_the_job_reused(engine, tmp_path: Path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        _, new_id = _regenerated(session, tmp_path)

    body = _client(engine, tmp_path).get(f"/runs/{new_id}/view").text

    assert "We ship on Friday." in body
    assert "No transcript yet" not in body


def test_reused_steps_say_so_and_the_page_says_how_to_run_them_again(
    engine, tmp_path: Path
) -> None:
    with Session(engine, expire_on_commit=False) as session:
        _, new_id = _regenerated(session, tmp_path)

    body = _client(engine, tmp_path).get(f"/runs/{new_id}/view").text

    assert body.count("Reused") >= len(STEPS)
    assert "every step was reused from the previous job" in body
    assert "Run every step again" in body


def test_removing_the_owner_hands_the_transcript_to_the_job_that_reads_it(
    engine, tmp_path: Path
) -> None:
    with Session(engine, expire_on_commit=False) as session:
        source_id, new_id = _regenerated(session, tmp_path)

        remove_run(session, tmp_path / "runs", source_id)

        assert session.scalar(select(Transcript)).produced_by_run_id == new_id


def test_run_every_step_again_adopts_nothing(tmp_path: Path) -> None:
    """With the box ticked the new job reuses no step, and still replaces this one."""
    queue = InMemoryQueue()
    client = regenerate_client(tmp_path, queue, RunState.SUCCEEDED)

    client.post(
        "/runs/run-1/regenerate",
        data={"workflow_name": "meeting-decisions", "rerun_all": "true"},
        follow_redirects=False,
    )

    run = new_run(tmp_path)
    assert run.reused_from_run_id is None
    assert run.replaces_run_id == "run-1"
