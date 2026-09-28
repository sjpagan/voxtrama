"""What execute_step sends to Ollama for a summarize step.

Reads the request body FakeTransport recorded, not the run's outcome: the
two facts this file proves (json_output's two fields travel together,
and no Segment.start value reaches the prompt) are about the request,
not about what comes back.
"""

from __future__ import annotations

import json
from urllib.request import Request

import pytest
from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.workflow.definition import Step, Workflow

OLLAMA_URL = "http://127.0.0.1:11434"


def _workflow(*steps: Step) -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=list(steps),
    )


def _transcript() -> Transcript:
    transcript = Transcript(
        id="t1",
        recording_id="r1",
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="low",
    )
    transcript.segments = [Segment(start=12.5, end=16.75, text="hello there", confidence=1.0)]
    return transcript


def _sent_generate_request(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Request:
    """Run one summarize step against the fake transport, and return what it sent."""
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", OLLAMA_URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    transport = install(monkeypatch)
    empty = json.dumps({"response": json.dumps({"key_points": []})}).encode()
    transport.route(f"{OLLAMA_URL}/api/generate", FakeResponse(200, empty))
    no_tags = json.dumps({"models": []}).encode()
    transport.route(f"{OLLAMA_URL}/api/tags", FakeResponse(200, no_tags))

    run = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow(step))
    context.transcript = _transcript()
    execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)

    # The last one is the step's own: before it, with no context declared,
    # the engine asks once to deduce one.
    return [c for c in transport.calls if c.full_url.endswith("/api/generate")][-1]


def test_json_output_sets_format_and_think_together_in_the_request(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = json.loads(_sent_generate_request(db_session, monkeypatch).data)

    assert sent["format"] == "json"
    assert sent["think"] is False


def test_the_prompt_carries_no_segment_timestamps(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = json.loads(_sent_generate_request(db_session, monkeypatch).data)["prompt"]

    assert "12.5" not in prompt
    assert "16.75" not in prompt
