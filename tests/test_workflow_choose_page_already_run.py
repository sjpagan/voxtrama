"""HTTP tests for GET /recordings/{id}/choose-workflow's own honest re-run notice
and "Already run"/View result. The header's own duration/speaker
line lives in test_workflow_choose_page_header.py, split apart for the same
reason (tests/test_architecture_limits.py).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    with Session(engine) as session:
        session.add(
            Recording(
                id="rec-1",
                original_filename="clip.wav",
                stored_path="recordings/clip.wav",
                content_sha256="0" * 64,
                duration_seconds=1.0,
                media_format="wav",
            )
        )
        session.commit()

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        data_dir=tmp_path, hardware_profile="base"
    )
    yield TestClient(app)
    get_settings.cache_clear()


def _cards(body: str) -> list[str]:
    """One workflow_choice_panel.html card's own markup per element, split on its
    outer `<div class="vx-card...`. A plain `.split('<div class="vx-card')` also
    cuts inside `.vx-card__header`, one level down. The lookahead below excludes
    it (the character right after "vx-card" there is "_", never a quote or space).
    """
    return re.split(r'<div class="vx-card(?=["\s])', body)[1:]


def _insert_run(tmp_path: Path, run_id: str, workflow_name: str, state: RunState) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                recording_id="rec-1",
                workflow_name=workflow_name,
                workflow_version="1.0.0",
                state=state,
            )
        )
        session.commit()


def test_a_first_choice_shows_no_restart_notice(client: TestClient) -> None:
    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "starts a brand-new job" not in body


def test_re_running_a_recording_that_already_has_a_run_shows_the_restart_notice(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(tmp_path, "run-1", "transcribe-only", RunState.SUCCEEDED)

    body = client.get("/recordings/rec-1/choose-workflow?workflow=meeting-decisions").text

    assert "starts a brand-new job" in body
    # A re-run's own breadcrumb still leads to Runs, not the library. Only
    # a first choice does (workflow_choose.py's own docstring on why one
    # signal tells the two doors apart).
    assert "/workflows?workflow=" not in body


def test_a_workflow_already_run_on_this_recording_offers_view_result_not_start(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(tmp_path, "run-1", "meeting-decisions", RunState.SUCCEEDED)

    body = client.get("/recordings/rec-1/choose-workflow").text

    cards = _cards(body)
    meeting_decisions = next(card for card in cards if "Meeting decisions" in card)
    transcribe_only = next(card for card in cards if "Transcribe only" in card)

    assert "Already run" in meeting_decisions
    assert 'href="/runs/run-1/view"' in meeting_decisions
    assert "Start job" not in meeting_decisions
    assert "Already run" not in transcribe_only
    assert "Start job" in transcribe_only


def test_a_workflow_still_running_is_not_shown_as_already_run(
    tmp_path: Path, client: TestClient
) -> None:
    _insert_run(tmp_path, "run-1", "meeting-decisions", RunState.RUNNING)

    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "Already run" not in body
