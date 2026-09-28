"""The home is the new-job form."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base

_SCRIPT = Path(__file__).resolve().parents[1] / "src/voxtrama/web/static/js/new_job.js"


@pytest.fixture
def body(tmp_path: Path) -> Iterator[str]:
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(
        data_dir=tmp_path, ollama_model="llama3.1:8b"
    )
    yield TestClient(app).get("/").text


def test_the_home_is_a_form_that_creates_a_job(body: str) -> None:
    assert "<h1>New job</h1>" in body
    assert 'action="/jobs"' in body
    assert 'enctype="multipart/form-data"' in body
    assert 'name="files"' in body and "multiple" in body


def test_the_three_system_workflows_are_cards_and_transcribe_only_is_an_option(body: str) -> None:
    cards = re.findall(r'name="workflow_name" value="([^"]+)"', body)

    assert cards[0] == "meeting-decisions"
    assert set(cards) == {"meeting-decisions", "lesson-companion", "research-interview"}
    assert 'name="transcribe_only"' in body


def test_advanced_is_closed_and_starts_from_the_installation_s_values(body: str) -> None:
    assert '<details class="vx-advanced">' in body
    assert 'name="summary_detail" min="1" max="5" step="1" value="3"' in body
    assert 'value="llama3.1:8b" selected' in body
    assert body.count("data-tag") == 8  # recap language, delete after


def test_the_video_address_field_is_gone(body: str) -> None:
    assert "/recordings/from-urls" not in body
    assert "youtube" not in body.lower()


def test_the_status_row_and_the_hero_left_the_home(body: str) -> None:
    assert "vx-status-row" not in body
    assert "vx-hero" not in body


@pytest.mark.parametrize("key", ["changed", "default", "parts", "part", "cores", "cores-of"])
def test_every_string_the_script_reads_is_on_the_page(body: str, key: str) -> None:
    assert f'data-key="{key}"' in body
    assert f"strings[{key!r}]".replace("'", '"') in _SCRIPT.read_text() or key in (
        _SCRIPT.read_text()
    )
