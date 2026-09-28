"""engine.summarize's step, run through execute_step: anchoring and provenance.

Exercises engine.builtin's real "summarize" registration end to end, with
Ollama's HTTP faked by tests/fakes/http_transport.py: no real model, no
network, but the exact wiring execute_run drives in production:
validate_output, anchor_output, and now provider selection too. Failure
paths (missing model, local_only) live in test_engine_summarize_errors.py.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.db.models.step import StepState
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.workflow.definition import Step, Workflow

OLLAMA_URL = "http://127.0.0.1:11434"


def _ok(body: dict) -> FakeResponse:
    return FakeResponse(200, json.dumps(body).encode())


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
    transcript.segments = [
        Segment(start=0.0, end=2.0, text="hello there", confidence=1.0),
        Segment(start=2.0, end=4.0, text="general kenobi", confidence=1.0),
        Segment(start=4.0, end=6.0, text="you are a bold one", confidence=1.0),
    ]
    return transcript


def _route_ollama(transport, key_points: list[dict]) -> None:
    body = {"key_points": key_points}
    transport.route(f"{OLLAMA_URL}/api/generate", _ok({"response": json.dumps(body)}))
    transport.route(
        f"{OLLAMA_URL}/api/tags", _ok({"models": [{"name": "qwen-test", "digest": "sha256:x"}]})
    )


def _prepared(db_session: Session):
    """A committed Run and its one "summarize" step, ready for execute_step."""
    run = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow(step))
    context.transcript = _transcript()
    return step, rows[0], context


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", OLLAMA_URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")


def test_three_quotes_found_in_the_transcript_all_anchor(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    transport = install(monkeypatch)
    _route_ollama(
        transport,
        [
            {"text": "a greeting", "quote": "hello there"},
            {"text": "a reply", "quote": "general kenobi"},
            {"text": "a remark", "quote": "you are a bold one"},
        ],
    )
    step, row, context = _prepared(db_session)

    execute_step(context, step, row, BUILTIN_STEPS, BUILTIN_SKILLS)

    key_points = context.produced["summarize"]["key_points"]
    assert row.state == StepState.SUCCEEDED
    assert all(point["needs_review"] is False for point in key_points)
    assert [point["evidence"] for point in key_points] == [
        {"start": 0.0, "end": 2.0},
        {"start": 2.0, "end": 4.0},
        {"start": 4.0, "end": 6.0},
    ]


def test_a_quote_not_in_the_transcript_needs_review_and_the_run_still_succeeds(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # SUMMARIZE.evidence_required is False: one bad citation out of
    # several must not fail the whole step, only mark itself.
    _configure(monkeypatch)
    transport = install(monkeypatch)
    _route_ollama(
        transport,
        [
            {"text": "a greeting", "quote": "hello there"},
            {"text": "invented", "quote": "nothing like this was said"},
        ],
    )
    step, row, context = _prepared(db_session)

    execute_step(context, step, row, BUILTIN_STEPS, BUILTIN_SKILLS)

    key_points = context.produced["summarize"]["key_points"]
    assert row.state == StepState.SUCCEEDED
    assert key_points[0]["needs_review"] is False
    assert key_points[1]["needs_review"] is True
    assert key_points[1]["evidence"] is None


def test_the_context_records_which_model_produced_the_step(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    transport = install(monkeypatch)
    _route_ollama(transport, [{"text": "a greeting", "quote": "hello there"}])
    step, row, context = _prepared(db_session)

    execute_step(context, step, row, BUILTIN_STEPS, BUILTIN_SKILLS)

    provenance = context.models["summarize"]
    assert provenance.provider == "ollama"
    assert provenance.model == "qwen-test"
    assert provenance.remote is False
    # The same fields land on the row itself: test_engine_step_
    # model_provenance.py covers that at length, through a real two-step run.
    assert row.model == "qwen-test"
