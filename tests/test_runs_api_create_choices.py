"""POST /runs with `choices`: the rule_rejected path.

Split out of test_runs_api_create.py, which covers everything about the
route that is not about choices. Same split, and for the same reason,
as test_manifest_builder.py/test_manifest_sections.py in this suite.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user, stamp_head
from fakes.queue import InMemoryQueue
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_engine, get_queue
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run

# A step that restricts generative_model: `transcribe` is a real
# built-in skill, so the workflow loads, but the check that rejects the
# choice below cares only about allows.models, not about what the skill does.
_WORKFLOW_NAME = "post-runs-choice-workflow"
_WORKFLOW_YAML = """\
name: post-runs-choice-workflow
version: 1.0.0
schema_version: v1
description: Test-only workflow for a rejected run choice.
steps:
  - id: transcribe
    skill: transcribe
    skill_version: "1.0.0"
    allows:
      models: ["allowed-model"]
"""


@pytest.fixture
def queue() -> InMemoryQueue:
    return InMemoryQueue()


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, queue: InMemoryQueue
) -> Iterator[TestClient]:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / f"{_WORKFLOW_NAME}.yaml").write_text(_WORKFLOW_YAML)

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    stamp_head(engine)  # POST /runs now refuses a schema behind Alembic's head

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[get_engine] = lambda: engine
    yield TestClient(app)
    get_settings.cache_clear()


def _insert_recording(tmp_path: Path, recording_id: str) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        session.add(
            Recording(
                id=recording_id,
                original_filename="clip.wav",
                stored_path="recordings/clip.wav",
                content_sha256="0" * 64,
                duration_seconds=1.0,
                media_format="wav",
            )
        )
        session.commit()


def test_post_runs_422_rule_rejected_when_a_choice_widens_a_declared_constraint(
    tmp_path: Path, client: TestClient
) -> None:
    """The rejection precedes creation, not
    a cleanup after it. Checked here directly against the database, not
    only inferred from the response.
    """
    _insert_recording(tmp_path, "rec-4")

    response = client.post(
        "/runs",
        json={
            "workflow_name": _WORKFLOW_NAME,
            "recording_id": "rec-4",
            "choices": {"generative_model": "not-allowed"},
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "rule_rejected"
    # The detail must name the step, the field and the value refused,
    # not a bare "invalid choice".
    assert "generative_model" in body["detail"]
    assert "transcribe" in body["detail"]
    assert response.headers["content-type"] == "application/problem+json"

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    with Session(engine) as session:
        assert session.scalars(select(Run).where(Run.recording_id == "rec-4")).first() is None
