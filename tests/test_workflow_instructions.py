"""What a generative step asks the model: read on system workflows, written on custom ones."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fakes.workflows_client import workflows_client
from fastapi.testclient import TestClient

from voxtrama.engine.skill_catalog import load_named_skill_file
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.instructions import (
    InstructionsError,
    check_instructions,
    step_instructions,
)

SHIPPED = load_named_skill_file("summarize").prompt
MINE = (
    "Write three bullet points in {language} as JSON key_points with text and quote.\n{transcript}"
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from workflows_client(tmp_path, monkeypatch)


def _detail(client: TestClient, name: str) -> str:
    body = client.get(f"/workflows?workflow={name}").text
    return body[body.index('id="vx-workflow-detail"') :]


def test_a_system_workflow_shows_what_each_step_asks_read_only(client) -> None:
    detail = _detail(client, "meeting-decisions")

    assert "What each step asks the model" in detail
    assert '<mark class="vx-wf-slot">{transcript}</mark>' in detail
    assert "key_points (text, quote)" in detail
    assert "decisions (decision, owner, deadline, quote)" in detail
    assert "read-only: duplicate it to write your own" in detail
    assert "<textarea" not in detail


def test_the_custom_form_starts_from_the_system_instructions(client) -> None:
    form = client.get("/workflows/new?source=meeting-decisions").text

    assert 'name="instructions:summarize"' in form
    assert "Summarize the transcript below as a JSON object" in form
    assert 'name="instructions:transcribe"' not in form  # it asks no model anything


def _save(client: TestClient, text: str):
    return client.post(
        "/workflows/custom",
        data={
            "title": "Short recap",
            "skill": ["diarize:1.0.0", "summarize:1.0.0"],
            "instructions:summarize": text,
        },
        follow_redirects=False,
    )


def test_edited_instructions_are_kept_on_the_step_not_on_the_skill(client, tmp_path) -> None:
    assert _save(client, MINE).status_code == 303

    saved = yaml.safe_load((tmp_path / "workflows" / "short-recap.yaml").read_text())
    summarize = next(step for step in saved["steps"] if step["id"] == "summarize")
    assert summarize["instructions"].strip() == MINE
    assert load_named_skill_file("summarize").prompt == SHIPPED
    assert not (tmp_path / "skills").exists()
    detail = _detail(client, "short-recap")
    assert "Write three bullet points" in detail and ">Edited<" in detail


def test_unchanged_instructions_are_not_copied(client, tmp_path) -> None:
    _save(client, SHIPPED.replace("\n", "\r\n"))

    saved = yaml.safe_load((tmp_path / "workflows" / "short-recap.yaml").read_text())
    assert all(not step.get("instructions") for step in saved["steps"])


@pytest.mark.parametrize("text", ["No transcript here.", "{transcript} and a {stray} brace"])
def test_instructions_that_cannot_run_are_refused(client, text) -> None:
    response = _save(client, text)

    assert response.status_code == 422
    with pytest.raises(InstructionsError):
        check_instructions(text)


def test_the_engine_uses_them_only_while_the_step_runs_that_skill() -> None:
    own = Step(id="s", skill="summarize", skill_version="1.0.0", instructions=MINE)
    workflow = Workflow(name="w", version="1", schema_version="v1", description="d", steps=[own])
    swapped = own.model_copy(update={"skill": "extract_themes"})

    assert step_instructions(workflow, [own]) == {"s": MINE}
    assert step_instructions(workflow, [swapped]) == {}
