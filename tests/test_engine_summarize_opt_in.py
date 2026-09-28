"""An opt-in test of engine.summarize against a real Ollama server.

Same shape as tests/test_providers_opt_in.py: skip on a missing
environment variable rather than fail, so the suite stays green on a
machine with no such server reachable. Green here does not mean
"verified against a real provider", only "not disproven by one".
"""

from __future__ import annotations

import os

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy.orm import Session

from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run


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
        Segment(start=0.0, end=3.0, text="We will ship the report by Friday.", confidence=1.0),
        Segment(
            start=3.0, end=6.0, text="January clashes with the trade fair though.", confidence=1.0
        ),
    ]
    return transcript


def test_summarize_against_a_real_ollama_server(db_session: Session) -> None:
    if not os.environ.get("VOXTRAMA_OLLAMA_URL"):
        pytest.skip("VOXTRAMA_OLLAMA_URL is not set: no real Ollama to test against")
    if not os.environ.get("VOXTRAMA_OLLAMA_MODEL"):
        pytest.skip("VOXTRAMA_OLLAMA_MODEL is not set: no model to ask for a summary")

    run = create_run(db_session, "test-workflow", "unpinned")
    # current_step_id is what engine.preparation sets around a real step.
    # Here the caller names it outright. That is why it is a field on the
    # context rather than something read out of the logger.
    context = ExecutionContext(
        session=db_session, run=run, transcript=_transcript(), current_step_id="summarize"
    )

    output = BUILTIN_STEPS["summarize"](context)

    Draft202012Validator(BUILTIN_SKILLS["summarize"]["1.0.0"].output_schema).validate(output)
