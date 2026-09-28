"""A generative step that fails after the model already answered keeps its provenance.

A failed run's manifest exists, and it is the most important
one of all. Split from test_engine_step_model_provenance.py, which covers
the successful path, because this is a distinct case that has to be
proved, not deduced from the success case.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.db.models.step import StepState
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.workflow.definition import Step, Workflow

OLLAMA_URL = "http://127.0.0.1:11434"


def _workflow() -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="summarize", skill="summarize", skill_version="1.0.0")],
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
    transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1.0)]
    return transcript


def _route_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """The model answers with valid JSON that does not match summarize's own
    output_schema (no "key_points"): validate_output raises
    OutputSchemaViolation *after* provider.generate already returned, and
    engine.progress.record_provenance already committed, not before.
    """
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", OLLAMA_URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    transport = install(monkeypatch)
    malformed = {"not_key_points": []}
    transport.route(
        f"{OLLAMA_URL}/api/generate",
        FakeResponse(200, json.dumps({"response": json.dumps(malformed)}).encode()),
    )
    transport.route(
        f"{OLLAMA_URL}/api/tags",
        FakeResponse(
            200, json.dumps({"models": [{"name": "qwen-test", "digest": "sha256:x"}]}).encode()
        ),
    )


def test_a_step_that_fails_output_validation_after_the_model_answered_keeps_its_provenance(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS

    _route_malformed_response(monkeypatch)
    run = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow())
    context.transcript = _transcript()

    with pytest.raises(Exception, match="output"):
        execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)

    row = rows[0]
    assert row.state != StepState.SUCCEEDED
    assert row.model == "qwen-test"
    assert row.model_revision == "sha256:x"
    assert row.provider == "ollama"
    assert row.host == "127.0.0.1:11434"
    assert row.profile_check_skipped is False

    # Read back through a second, independent session: what committed, not
    # what the in-process object still happens to hold: the same
    # durability engine.reconcile_manifest depends on after a crash.
    db_session.expire_all()
    reread = db_session.get(type(row), row.id)
    assert reread.model == "qwen-test"
    assert reread.provider == "ollama"
