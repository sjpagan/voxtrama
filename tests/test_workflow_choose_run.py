"""HTTP tests for POST /recordings/{id}/runs: starting a Run from the choice
panel and landing on its page, plus the coherence
check: an option this route accepts is one the panel offered.

GET /recordings/{id}/choose-workflow itself lives in test_workflow_choose_page.py,
split apart for the project's line limit (tests/test_architecture_limits.py).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.queue import InMemoryQueue
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_queue
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run


@pytest.fixture
def queue() -> InMemoryQueue:
    return InMemoryQueue()


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, queue: InMemoryQueue
) -> Iterator[TestClient]:
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
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = lambda: queue
    yield TestClient(app)
    get_settings.cache_clear()


def test_choosing_transcribe_only_starts_a_run_and_lands_on_its_page(
    client: TestClient, queue: InMemoryQueue
) -> None:
    response = client.post(
        "/recordings/rec-1/runs",
        data={"workflow_name": "transcribe-only"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/runs/")
    assert location.endswith("/view")

    landing = client.get(location)
    assert landing.status_code == 200
    assert len(queue._jobs) == 1


def test_choosing_a_generative_model_meeting_decisions_allows_is_accepted(
    client: TestClient,
) -> None:
    """The exact value the panel offers for this workflow (its own generative_models,
    computed by the same workflow_choices_for the panel renders from) is one
    engine.enqueue.enqueue_run's own check_choices accepts underneath this route.
    """
    response = client.post(
        "/recordings/rec-1/runs",
        data={"workflow_name": "meeting-decisions", "generative_model": "qwen3:30b"},
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_a_generative_model_meeting_decisions_does_not_allow_is_rejected(
    client: TestClient,
) -> None:
    response = client.post(
        "/recordings/rec-1/runs",
        data={"workflow_name": "meeting-decisions", "generative_model": "not-a-real-model"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "rule_rejected"


def test_a_recording_that_does_not_exist_is_404(client: TestClient) -> None:
    response = client.post(
        "/recordings/no-such-recording/runs", data={"workflow_name": "transcribe-only"}
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_the_run_is_written_with_the_recording_it_was_chosen_for(
    client: TestClient, tmp_path: Path
) -> None:
    client.post(
        "/recordings/rec-1/runs", data={"workflow_name": "transcribe-only"}, follow_redirects=False
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        run = session.scalars(select(Run).where(Run.recording_id == "rec-1")).one()
        assert run.workflow_name == "transcribe-only"
