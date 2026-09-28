"""HTTP tests for POST /workflows/{name}/steps:
changing a step's own skill among the alternatives the workflow already
declares, saved through workflow.document_write, never written at
all when the result would not validate.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import voxtrama.api.routes.workflow_edit as workflow_edit
from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SHIPPED_FILE = _REPO_ROOT / "workflows" / "meeting-decisions.yaml"


def _step_index(skill: str) -> int:
    """Position of the step that uses `skill` in the workflow shipped with the repo."""
    definition = yaml.safe_load(_SHIPPED_FILE.read_text())
    return next(i for i, step in enumerate(definition["steps"]) if step["skill"] == skill)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # save_document and document_roots both read the process-wide
    # get_settings() directly, not FastAPI's own DI (test_document_write.py's
    # own fixture shape). The env var is what steers them. The override
    # below only covers a route's own Depends(get_settings).
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)
    get_settings.cache_clear()


def test_saving_a_declared_alternative_persists_and_is_read_back(
    client: TestClient, tmp_path: Path
) -> None:
    shipped_before = _SHIPPED_FILE.read_bytes()

    response = client.post(
        "/workflows/meeting-decisions/steps",
        data={"step_skill__extract_decisions": "extract_themes:1.0.0"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/workflows?workflow=meeting-decisions"
    saved = tmp_path / "workflows" / "meeting-decisions.yaml"
    assert saved.is_file()
    assert "extract_themes" in saved.read_text()
    # The shipped file in the package's own checkout is never touched:
    # editing writes a covering copy in the data directory.
    assert _SHIPPED_FILE.read_bytes() == shipped_before

    body = client.get("/workflows?workflow=meeting-decisions").text
    assert "extract_themes 1.0.0" in body


def test_a_skill_the_step_does_not_allow_is_rejected_naming_the_step(
    client: TestClient, tmp_path: Path
) -> None:
    """summarize is a real, loadable skill, just not one
    meeting-decisions.yaml lists among extract_decisions' own alternatives.
    """
    response = client.post(
        "/workflows/meeting-decisions/steps",
        data={"step_skill__extract_decisions": "summarize:1.0.0"},
        follow_redirects=False,
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "rule_rejected"
    assert "extract_decisions" in body["detail"]
    assert not (tmp_path / "workflows").exists()


def test_an_edit_that_would_invalidate_the_workflow_is_rejected_and_nothing_is_written(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The alternatives gate is the first line of defence; this proves the
    deeper validate_workflow check underneath it also holds, naming the
    step and leaving the data directory untouched: the "never
    invalid" rule.
    """

    def _fake_allowed(_workflow: object) -> dict[str, set[tuple[str, str]]]:
        return {"extract_decisions": {("does-not-exist", "9.9.9")}}

    monkeypatch.setattr(workflow_edit, "_allowed_alternatives", _fake_allowed)

    response = client.post(
        "/workflows/meeting-decisions/steps",
        data={"step_skill__extract_decisions": "does-not-exist:9.9.9"},
        follow_redirects=False,
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_failed"
    # workflow.loader names the step by its position, not its id, so the
    # expected index is read from the shipped file instead of written here:
    # pinning it to "steps[2]" turned this test red the day a new step was
    # added before extract_decisions, with nothing this test checks
    # having changed.
    assert f"steps[{_step_index('extract_decisions')}]" in body["detail"]
    assert "does-not-exist" in body["detail"]
    assert not (tmp_path / "workflows").exists()


def test_editing_an_unknown_workflow_name_is_422(client: TestClient) -> None:
    response = client.post("/workflows/does-not-exist/steps", data={}, follow_redirects=False)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
