"""Tests for GET /runs/{id}/view's succeeded-state result section.

Split from test_web_run_page.py, which covers the page's static shell,
kept apart for the same reason test_web_run_page_failure.py already is.
test_web_run_page_result_empty.py is the same split again, one level
further, for a workflow with no generative step at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.run_result import (
    build_app,
    insert_recording_and_transcript,
    insert_run,
)
from fakes.run_result import (
    write_manifest_and_output as write_manifest,
)
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from voxtrama.db.models.step import RunStep, StepState

_DECISION = {
    "decision": "Ship the new onboarding flow on 7 October.",
    "quote": "we'll ship it on 7 october",
    "evidence": {"start": 754.0, "end": 761.0},
    "needs_review": False,
}


@pytest.fixture
def app_engine(tmp_path: Path) -> tuple[TestClient, Engine]:
    app, engine = build_app(tmp_path)
    return TestClient(app), engine


def _decision_step(run_id: str) -> RunStep:
    return RunStep(
        run_id=run_id,
        step_id="extract_decisions",
        skill="extract_decisions",
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=0,
        attempts=1,
        model="llama3.1:8b",
    )


def test_a_succeeded_run_shows_the_player_and_the_transcript(
    tmp_path: Path, app_engine: tuple[TestClient, Engine]
) -> None:
    client, engine = app_engine
    step = _decision_step("run-1")
    run = insert_run(engine, "run-1", "meeting-decisions", step)
    insert_recording_and_transcript(engine, "run-1")
    write_manifest(tmp_path, run, [step], {"extract_decisions": {"decisions": [_DECISION]}})

    body = client.get("/runs/run-1/view").text

    assert 'id="vx-run-result"' in body
    assert 'src="/recordings/rec-run-1/audio"' in body
    assert "We&#39;ll ship it on 7 October." in body  # escaped, as all page text is
    assert 'id="vx-run-terminal"' not in body


def test_the_player_menu_offers_the_audio_to_download(
    tmp_path: Path, app_engine: tuple[TestClient, Engine]
) -> None:
    """The «⋮» at the far right of the player."""
    client, engine = app_engine
    step = _decision_step("run-2")
    run = insert_run(engine, "run-2", "meeting-decisions", step)
    insert_recording_and_transcript(engine, "run-2")
    write_manifest(tmp_path, run, [step], {"extract_decisions": {"decisions": [_DECISION]}})

    body = client.get("/runs/run-2/view").text
    menu = body.split('class="vx-player__menu"')[1].split("</details>")[0]

    assert 'href="/recordings/rec-run-2/audio" download' in menu


def test_a_result_carries_its_own_evidence_link_and_provenance(
    tmp_path: Path, app_engine: tuple[TestClient, Engine]
) -> None:
    client, engine = app_engine
    step = _decision_step("run-2")
    run = insert_run(engine, "run-2", "meeting-decisions", step)
    insert_recording_and_transcript(engine, "run-2")
    write_manifest(tmp_path, run, [step], {"extract_decisions": {"decisions": [_DECISION]}})

    body = client.get("/runs/run-2/view").text

    assert 'data-evidence-start="754.0"' in body
    assert 'data-evidence-end="761.0"' in body
    assert "12:34" in body and "12:41" in body
    assert "meeting-decisions" in body and "extract_decisions" in body and "llama3.1:8b" in body


def test_regenerate_job_opens_a_panel_filled_with_this_jobs_values(
    tmp_path: Path, app_engine: tuple[TestClient, Engine]
) -> None:
    """«Regenerate job» replaces the earlier «Change workflow» on the chain.
    The panel posts to /runs/{id}/regenerate with this job's own workflow
    already selected."""
    client, engine = app_engine
    step = _decision_step("run-3")
    run = insert_run(engine, "run-3", "meeting-decisions", step)
    insert_recording_and_transcript(engine, "run-3")
    write_manifest(tmp_path, run, [step], {"extract_decisions": {"decisions": [_DECISION]}})

    body = client.get("/runs/run-3/view").text

    assert 'action="/runs/run-3/regenerate"' in body
    assert "switch-workflow" not in body
    assert '<option value="meeting-decisions" selected>' in body
    assert 'name="summary_detail"' in body


def test_the_page_carries_what_links_a_passage_back_to_its_claims(
    tmp_path: Path, app_engine: tuple[TestClient, Engine]
) -> None:
    """The second direction: a transcript row must carry its own interval,
    and run_evidence.js must load before run_result.js calls into it.

    The linking itself is client-side and no test here can click it. This
    guards that the page ships the two halves the browser needs: the
    intervals on both columns, and the script order `defer` respects.
    """
    client, engine = app_engine
    step = _decision_step("run-4")
    run = insert_run(engine, "run-4", "meeting-decisions", step)
    insert_recording_and_transcript(engine, "run-4")
    write_manifest(tmp_path, run, [step], {"extract_decisions": {"decisions": [_DECISION]}})

    body = client.get("/runs/run-4/view").text

    assert "data-start=" in body and "data-end=" in body
    assert 'id="vx-output-linked"' in body
    assert body.index("js/run_evidence.js") < body.index("js/run_result.js")
