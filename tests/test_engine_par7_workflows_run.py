"""The three example workflows, each run to its generative step.

Loads the real workflow files under workflows/ through load_named_workflow
(the same registry a production run uses) and drives their last step
(extract_decisions, extract_concepts or extract_themes) through
engine.preparation exactly as test_engine_summarize_run.py drives
"summarize": Ollama's HTTP faked by tests/fakes/http_transport.py, no real
model, no network. transcribe and diarize are not re-run here (they have
their own tests), only the new extract_* step each one adds.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.db.models.step import StepState
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.catalog import load_named_workflow
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run

OLLAMA_URL = "http://127.0.0.1:11434"

# (workflow name, field the skill produces, one item shaped as that skill's
# output_schema requires). The quote in each item must match _transcript().
CASES = [
    (
        "meeting-decisions",
        "decisions",
        {"decision": "ship it", "owner": "Alice", "deadline": "Friday", "quote": "hello there"},
    ),
    (
        "lesson-companion",
        "concepts",
        {"concept": "gravity", "definition": "a force", "quote": "hello there"},
    ),
    (
        "research-interview",
        "themes",
        {"theme": "trust", "insight": "trust took time to build", "quote": "hello there"},
    ),
]


def _ok(body: dict) -> FakeResponse:
    return FakeResponse(200, json.dumps(body).encode())


def _transcript() -> Transcript:
    transcript = Transcript(
        id="t1",
        recording_id="r1",
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="low",
    )
    transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1.0)]
    return transcript


def _route_ollama(transport, body: dict) -> None:
    transport.route(f"{OLLAMA_URL}/api/generate", _ok({"response": json.dumps(body)}))
    transport.route(
        f"{OLLAMA_URL}/api/tags", _ok({"models": [{"name": "qwen-test", "digest": "sha256:x"}]})
    )


@pytest.mark.parametrize("workflow_name, field, item", CASES)
def test_the_workflows_extractor_step_runs_and_its_quote_anchors(
    workflow_name: str, field: str, item: dict, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", OLLAMA_URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    transport = install(monkeypatch)
    _route_ollama(transport, {field: [item]})

    workflow = load_named_workflow(workflow_name)
    run = create_run(db_session, workflow_name, "unpinned")
    _, rows, context, _ = prepare_run(db_session, run, workflow)
    context.transcript = _transcript()
    extract_step, extract_row = workflow.steps[-1], rows[-1]

    execute_step(context, extract_step, extract_row, BUILTIN_STEPS, BUILTIN_SKILLS)

    claims = context.produced[extract_step.id][field]
    assert extract_row.state == StepState.SUCCEEDED
    assert claims[0]["needs_review"] is False
    assert claims[0]["evidence"] == {"start": 0.0, "end": 2.0}
