"""A long transcript read in windows by any generative step, the outputs joined."""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path

import pytest
from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.models.step import StepState
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.generative import run_generative
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.workflow.loader import SkillRegistry, load_workflow
from voxtrama.workflow.skill_file import load_skill_file

OLLAMA_URL = "http://127.0.0.1:11434"
SUMMARIZE = Path(__file__).resolve().parents[1] / "skills" / "summarize.yaml"
LINE = "We agreed to ship the importer on Friday after the review. " * 8

_WORKFLOW = """\
name: summary-only
version: 1.0.0
schema_version: v1
description: Only a summary.
steps:
  - id: summarize
    skill: summarize
    skill_version: 1.0.0
"""


class _EveryTime(FakeResponse):
    """The same answer to every call: each `with` block reads a fresh copy."""

    def __enter__(self) -> FakeResponse:
        return FakeResponse(self.status, self.body)


def _transcript(lines: int) -> Transcript:
    transcript = Transcript(
        id="t1",
        recording_id="r1",
        language="en",
        model_name="w",
        model_revision="v1",
        hardware_profile="low",
    )
    transcript.segments = [
        Segment(start=i * 30.0, end=i * 30.0 + 28.0, text=f"{i}: {LINE}", confidence=1.0)
        for i in range(lines)
    ]
    transcript.segments[3].text += " Marco signs the contract today."
    return transcript


def _run(tmp_path: Path, db_session: Session, monkeypatch: pytest.MonkeyPatch, lines: int):
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", OLLAMA_URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    # One window at a time: the prompts below are read in the order they were sent.
    monkeypatch.setenv("VOXTRAMA_PARALLEL_WINDOWS", "1")
    get_settings.cache_clear()
    transport = install(monkeypatch)
    point = {"text": "The importer ships on Friday.", "quote": "Marco signs the contract today"}
    body = json.dumps({"response": json.dumps({"key_points": [point]})}).encode()
    transport.route(f"{OLLAMA_URL}/api/generate", _EveryTime(200, body))
    tags = {"models": [{"name": "qwen-test", "digest": "sha256:x"}]}
    transport.route(f"{OLLAMA_URL}/api/tags", FakeResponse(200, json.dumps(tags).encode()))
    skill_file = load_skill_file(SUMMARIZE)
    registry: SkillRegistry = {"summarize": {"1.0.0": skill_file.skill}}
    (tmp_path / "w.yaml").write_text(_WORKFLOW)
    workflow = load_workflow(tmp_path / "w.yaml", registry)
    run = create_run(db_session, "summary-only", "unpinned")
    steps, rows, context, _ = prepare_run(db_session, run, workflow)
    context.transcript = _transcript(lines)
    execute_step(
        context, steps[0], rows[0], {"summarize": partial(run_generative, skill_file)}, registry
    )
    prompts = [
        json.loads(call.data)["prompt"]
        for call in transport.calls
        if call.full_url.endswith("/api/generate")
        and not json.loads(call.data)["prompt"].startswith("Below are excerpts")  # deduction call
    ]
    return rows[0], context, prompts


def test_a_short_transcript_is_one_call_as_before(tmp_path, db_session, monkeypatch) -> None:
    row, context, prompts = _run(tmp_path, db_session, monkeypatch, lines=5)

    assert len(prompts) == 1
    assert "[The part to work on]" not in prompts[0]
    assert row.transcript_windows == 1


def test_a_long_transcript_is_read_window_by_window(tmp_path, db_session, monkeypatch) -> None:
    row, context, prompts = _run(tmp_path, db_session, monkeypatch, lines=80)

    assert row.state == StepState.SUCCEEDED
    assert row.transcript_windows == len(prompts) >= 3
    assert all("[The part to work on]" in prompt for prompt in prompts)
    assert "[Earlier in the recording, context only]" in prompts[1]
    assert f"one of {len(prompts)} parts of a longer recording" in prompts[0]
    # Every window found the same point: it is kept once, with its evidence.
    points = context.produced["summarize"]["key_points"]
    assert [p["text"] for p in points] == ["The importer ships on Friday."]
    assert points[0]["evidence"] is not None
