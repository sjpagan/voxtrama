"""HTTP tests for GET /workflows/{name}/choices.

Arithmetic-level cases (hardware_profiles' boundary, generative_models'
None-vs-[] distinction, and the coherence check against check_choices)
live in tests/test_workflow_choices_calc.py, split out for the same
reason as test_engine_choice_check.py/test_engine_choice_check_step_skills.py:
the project's line limit (tests/test_architecture_limits.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from voxtrama.api.app import create_app
from voxtrama.config.settings import get_settings

_NO_ALLOWS_WORKFLOW_NAME = "workflow-choices-no-allows"
_NO_ALLOWS_WORKFLOW_YAML = """\
name: workflow-choices-no-allows
version: 1.0.0
schema_version: v1
description: Test-only workflow that declares no allows anywhere.
steps:
  - id: transcribe
    skill: transcribe
    skill_version: "1.0.0"
  - id: diarize
    skill: diarize
    skill_version: "1.0.0"
    depends_on: [transcribe]
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / f"{_NO_ALLOWS_WORKFLOW_NAME}.yaml").write_text(
        _NO_ALLOWS_WORKFLOW_YAML
    )
    return TestClient(create_app())


def test_meeting_decisions_reports_the_alternatives_and_models_it_declares(
    client: TestClient,
) -> None:
    """Against the real shipped file, not an invented one: what it reports
    must be what workflows/meeting-decisions.yaml says.
    """
    response = client.get("/workflows/meeting-decisions/choices")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow"] == {"name": "meeting-decisions", "version": "2.0.0"}
    assert body["hardware_profiles"] == ["low", "base", "high"]
    assert body["generative_models"] == ["qwen2.5:0.5b", "qwen3:30b"]
    extract_decisions = next(s for s in body["steps"] if s["step_id"] == "extract_decisions")
    assert extract_decisions["skills"] == [{"skill": "extract_themes", "skill_version": "1.0.0"}]
    assert extract_decisions["models"] == ["qwen2.5:0.5b", "qwen3:30b"]
    transcribe = next(s for s in body["steps"] if s["step_id"] == "transcribe")
    assert transcribe["skills"] == []
    assert transcribe["models"] == []


def test_a_workflow_with_no_allows_reports_null_models_and_empty_step_lists(
    client: TestClient,
) -> None:
    response = client.get(f"/workflows/{_NO_ALLOWS_WORKFLOW_NAME}/choices")

    assert response.status_code == 200
    body = response.json()
    assert body["generative_models"] is None
    assert all(step["skills"] == [] and step["models"] == [] for step in body["steps"])


def test_a_workflow_name_that_does_not_resolve_is_422_validation_failed(
    client: TestClient,
) -> None:
    response = client.get("/workflows/does-not-exist/choices")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
