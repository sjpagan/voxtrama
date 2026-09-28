"""HTTP tests for GET /workflows.

Against the real shipped workflows, not invented ones (same discipline as
test_workflow_choose_page.py): the detail of meeting-decisions shows its
own four real steps, and every card lists the skills of its own workflow.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.workflows_client import card_of, workflows_client
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from workflows_client(tmp_path, monkeypatch)


def test_the_three_system_workflows_are_cards_and_transcribe_only_is_not(
    client: TestClient,
) -> None:
    body = client.get("/workflows").text

    assert body.count('<span class="vx-wf-tag">System</span>') >= 3
    assert "Turn a meeting into decisions, owners and next steps." in body
    assert "Transcribe only" not in body
    assert "3 system workflows" in body and "1 custom slot available" in body


def test_descriptions_are_one_line_for_a_person_not_internal_notes(client: TestClient) -> None:
    body = client.get("/workflows").text

    assert "ADR " not in body and "0.1 runs" not in body


def test_each_card_checks_off_what_its_own_steps_do(client: TestClient) -> None:
    body = client.get("/workflows").text

    lesson = card_of(body, "Lesson companion")
    meeting = card_of(body, "Meeting decisions")
    assert "Defines the key concepts" in lesson
    assert "Lists decisions and owners" not in lesson
    assert "Lists decisions and owners" in meeting
    assert "Tells the speakers apart" in meeting
    assert "vx-wf-chip" not in body and "extract_decisions</li>" not in body


def test_the_system_descriptions_are_the_same_length() -> None:
    """Nine words each, so the cards read alike side by side."""
    import yaml

    lengths = {
        len(yaml.safe_load(path.read_text())["description"].split())
        for path in (Path(__file__).parents[1] / "workflows").glob("*.yaml")
    }
    assert lengths == {9}


def test_the_detail_shows_meeting_decisions_own_real_steps_in_order(client: TestClient) -> None:
    body = client.get("/workflows?workflow=meeting-decisions").text
    detail = body[body.index('id="vx-workflow-detail"') :]

    titles = ["Transcribe", "Identify speakers", "Recap", "Extract decisions"]
    positions = [detail.index(f"<strong>{title}</strong>") for title in titles]
    assert positions == sorted(positions)
    assert "Verify evidence" not in detail and "Export" not in detail


def test_meeting_decisions_own_declared_alternative_is_offered_under_advanced(
    client: TestClient,
) -> None:
    body = client.get("/workflows?workflow=meeting-decisions").text

    assert "Advanced" in body
    assert 'value="extract_themes:1.0.0"' in body


def test_a_system_workflow_is_duplicated_never_edited(client: TestClient) -> None:
    meeting = card_of(client.get("/workflows").text, "Meeting decisions")

    assert 'href="/workflows/new?source=meeting-decisions"' in meeting
    assert "?edit=" not in meeting and "/delete" not in meeting
    assert client.get("/workflows/new?edit=meeting-decisions").status_code == 422
