"""Tests for GET /runs/{id}/view's succeeded-state result section on a
workflow with no generative step at all: transcribe-only.

Split from test_web_run_page_result.py, which drives the same page for a
workflow that does produce extracted output, kept apart so neither file
grows past the project's size limit.
"""

from __future__ import annotations

from pathlib import Path

from fakes.run_result import (
    build_app,
    insert_recording_and_transcript,
    insert_run,
)
from fakes.run_result import (
    write_manifest_and_output as write_manifest,
)
from fastapi.testclient import TestClient

from voxtrama.db.models.step import RunStep, StepState


def test_a_transcribe_only_run_shows_no_broken_looking_output_column(tmp_path: Path) -> None:
    app, engine = build_app(tmp_path)
    client = TestClient(app)
    step = RunStep(
        run_id="run-3",
        step_id="diarize",
        skill="diarize",
        skill_version="1.0.0",
        state=StepState.SUCCEEDED,
        position=0,
        attempts=1,
    )
    run = insert_run(engine, "run-3", "transcribe-only", step)
    insert_recording_and_transcript(engine, "run-3")
    write_manifest(tmp_path, run, [step], {})

    body = client.get("/runs/run-3/view").text

    assert 'id="vx-run-transcript"' in body
    assert 'id="vx-run-output"' in body
    assert "no extracted results" in body
