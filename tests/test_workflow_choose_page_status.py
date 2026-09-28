"""HTTP tests for GET /recordings/{id}/choose-workflow's own additions:
readable titles, what a workflow produces, the promise the recording stays
unchanged, and a workflow carried in from the library (pre-selected, dropped when
unrecognised, its own breadcrumb back to the library). The honest re-run notice,
"already_run"/View result and the header's own duration/speaker line live in
test_workflow_choose_page_already_run.py, split apart for the same reason
(tests/test_architecture_limits.py).
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


def test_the_panel_reads_readable_titles_not_file_names(client: TestClient) -> None:
    """`name` still travels (the hidden field POST /runs reads), but a
    person reads `title`."""
    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "Meeting decisions" in body
    assert 'value="meeting-decisions"' in body


def test_the_panel_declares_what_each_workflow_produces(client: TestClient) -> None:
    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "Produces:" in body
    assert "Decision" in body


def test_the_promise_that_the_recording_stays_unchanged_always_shows(client: TestClient) -> None:
    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "Your original recording and transcript stay unchanged." in body


def test_a_workflow_carried_in_from_the_library_is_pre_selected(client: TestClient) -> None:
    body = client.get("/recordings/rec-1/choose-workflow?workflow=meeting-decisions").text

    cards = _cards(body)
    selected = next(card for card in cards if "Meeting decisions" in card)
    assert "vx-workflow-card--selected" in selected


def test_an_unrecognised_workflow_name_is_dropped_not_selected(client: TestClient) -> None:
    body = client.get("/recordings/rec-1/choose-workflow?workflow=no-such-workflow").text

    assert "vx-workflow-card--selected" not in body


def test_a_workflow_carried_in_from_the_library_leads_the_breadcrumb_back_there(
    client: TestClient,
) -> None:
    """Arriving from the library with a workflow already chosen, and no
    prior Run to make this a re-run, the climb back leads to the library."""
    body = client.get("/recordings/rec-1/choose-workflow?workflow=meeting-decisions").text

    assert 'href="/workflows?workflow=meeting-decisions"' in body


def test_with_no_workflow_carried_in_the_breadcrumb_leads_to_jobs(client: TestClient) -> None:
    body = client.get("/recordings/rec-1/choose-workflow").text

    assert 'href="/jobs"' in body  # The Jobs section, not the home form
    assert "/workflows?workflow=" not in body
