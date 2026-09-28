"""The custom workflow of the Workflows page: duplicate, from scratch,
the edition's limit, edit in place and delete."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fakes.workflows_client import card_of, workflows_client
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from workflows_client(tmp_path, monkeypatch)


def test_duplicating_writes_a_custom_workflow_with_the_ticked_skills(
    client: TestClient, tmp_path: Path
) -> None:
    form = client.get("/workflows/new?source=meeting-decisions").text
    assert 'value="Meeting decisions (copy)"' in form

    response = client.post(
        "/workflows/custom",
        data={
            "source": "meeting-decisions",
            "title": "Team sync",
            "description": "Decisions and themes of our sync.",
            "skill": ["diarize:1.0.0", "extract_decisions:1.0.0", "extract_themes:1.0.0"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/workflows?workflow=team-sync"
    saved = yaml.safe_load((tmp_path / "workflows" / "team-sync.yaml").read_text())
    assert [step["id"] for step in saved["steps"]] == [
        "transcribe",
        "diarize",
        "extract_decisions",
        "extract_themes",
    ]
    # The step kept from meeting-decisions keeps its declared alternatives.
    assert saved["steps"][2]["allows"]["skills"] == [
        {"skill": "extract_themes", "skill_version": "1.0.0"}
    ]
    body = client.get("/workflows").text
    card = card_of(body, "Team sync")
    assert '<span class="vx-wf-tag">Custom</span>' in body
    assert 'href="/workflows/new?edit=team-sync"' in card


def test_from_scratch_transcription_is_always_the_first_step(
    client: TestClient, tmp_path: Path
) -> None:
    client.post("/workflows/custom", data={"title": "Just recap", "skill": "summarize:1.0.0"})

    saved = yaml.safe_load((tmp_path / "workflows" / "just-recap.yaml").read_text())
    assert [(s["id"], s["depends_on"]) for s in saved["steps"]] == [
        ("transcribe", []),
        ("summarize", ["transcribe"]),
    ]


def test_a_second_custom_workflow_is_refused_and_the_page_says_so(client: TestClient) -> None:
    client.post("/workflows/custom", data={"title": "First", "skill": "diarize:1.0.0"})

    refused = client.post("/workflows/custom", data={"title": "Second"})
    body = client.get("/workflows").text

    assert refused.status_code == 422
    assert "The custom workflow allowed is already in use" in body
    assert "1 custom workflow in use" in body


def test_the_custom_workflow_is_edited_in_place_and_deleted(
    client: TestClient, tmp_path: Path
) -> None:
    client.post("/workflows/custom", data={"title": "First", "skill": "diarize:1.0.0"})

    client.post(
        "/workflows/custom",
        data={"original": "first", "title": "First, renamed", "skill": "summarize:1.0.0"},
    )
    saved = yaml.safe_load((tmp_path / "workflows" / "first.yaml").read_text())
    assert saved["title"] == "First, renamed"
    assert [step["id"] for step in saved["steps"]] == ["transcribe", "summarize"]

    client.post("/workflows/first/delete")
    assert not (tmp_path / "workflows" / "first.yaml").exists()
    assert client.post("/workflows/meeting-decisions/delete").status_code == 422
