"""HTTP tests for GET /recordings/{id}/choose-workflow: what the panel shows.

Against the real shipped workflows, not invented ones: what this page shows has to be
what workflow_choices_for already computes for meeting-decisions.yaml,
the same discipline test_workflow_choices_route.py follows for the JSON route this
page reuses. POST /recordings/{id}/runs itself lives in test_workflow_choose_run.py,
split apart for the project's own line limit (tests/test_architecture_limits.py).
"""

from __future__ import annotations

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


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # No workflows/ directory of its own: the shipped four are found
    # through document_roots' package-root fallback, the same as
    # test_workflow_choices_route.py's real-file case.
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


def test_the_page_shows_every_shipped_workflow_by_its_description(client: TestClient) -> None:
    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "clip.wav" in body
    assert "Turn a meeting into decisions, owners and next steps." in body
    assert "Turn any recording into a transcript with its speakers." in body


def test_the_page_shows_meeting_decisions_own_allowed_alternatives(client: TestClient) -> None:
    """What the panel offers for meeting-decisions has to be what
    workflow_choices_for already computes for it: the generative
    models it allows, and the one step alternative it declares.
    """
    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "qwen2.5:0.5b" in body
    assert "qwen3:30b" in body
    assert 'value="extract_themes:1.0.0"' in body


def test_the_options_sit_behind_a_closed_details_labelled_with_the_installed_default(
    client: TestClient,
) -> None:
    """Added mid-build: run options live in a closed <details>, and the
    blank option names what already applies rather than leaving the
    provenance of "changed" versus "as configured" a mystery.
    """
    body = client.get("/recordings/rec-1/choose-workflow").text

    assert "<details" in body
    assert "As configured" in body
    assert "As configured (base)" in body


def test_a_recording_that_does_not_exist_is_404(client: TestClient) -> None:
    response = client.get("/recordings/no-such-recording/choose-workflow")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_a_workflow_that_fails_to_load_is_shown_unavailable_not_a_500(
    tmp_path: Path, client: TestClient
) -> None:
    """A workflow that never becomes a Workflow object at all (a
    missing skill, here) still gets a card, with the reason, never an exception
    that takes the whole page down with it.
    """
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "broken.yaml").write_text(
        "name: broken\n"
        "version: 1.0.0\n"
        "schema_version: v1\n"
        "description: Deliberately broken for this test.\n"
        "steps:\n"
        "  - id: a\n"
        "    skill: does-not-exist\n"
        '    skill_version: "1.0.0"\n'
    )

    response = client.get("/recordings/rec-1/choose-workflow")

    assert response.status_code == 200
    assert "broken" in response.text
    assert "does-not-exist" in response.text
