"""engine.summarize's failure paths: missing model config, and local_only.

Companion to test_engine_summarize_run.py, split out to stay under the
project's file-size limit: that file covers anchoring and provenance on a
step that succeeds, this one covers what stops it before it does.
"""

from __future__ import annotations

import pytest
from fakes.http_transport import install
from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.context import StepPreconditionError
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.generative import OllamaModelNotConfiguredError
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.providers.base import PrivacyViolation
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.skill import Privacy


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
    transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1.0)]
    return transcript


def _prepared(db_session: Session):
    """A committed Run and its one "summarize" step, ready for execute_step."""
    run = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow(step))
    context.transcript = _transcript()
    return step, rows[0], context


def test_missing_ollama_model_fails_naming_the_variable(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.delenv("VOXTRAMA_OLLAMA_MODEL", raising=False)
    step, row, context = _prepared(db_session)

    with pytest.raises(OllamaModelNotConfiguredError, match="VOXTRAMA_OLLAMA_MODEL"):
        execute_step(context, step, row, BUILTIN_STEPS, BUILTIN_SKILLS)


def test_local_only_with_a_remote_provider_never_touches_the_transport(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", "https://ollama.example.com")
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    transport = install(monkeypatch)
    step, row, context = _prepared(db_session)
    # Declared after prepare_run, which would refuse it outright:
    # this is the last guard, at the call itself.
    monkeypatch.setattr(BUILTIN_SKILLS["summarize"]["1.0.0"], "privacy", Privacy.LOCAL_ONLY)

    with pytest.raises(PrivacyViolation):
        execute_step(context, step, row, BUILTIN_STEPS, BUILTIN_SKILLS)

    assert transport.calls == []


def test_a_step_run_outside_the_engine_never_reaches_the_provider(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    """current_step_id is None only when nothing set it: outside execute_step.

    It is checked before the provider is asked anything. Reading the step id
    out of the logging context instead would raise a bare
    KeyError naming neither what is missing nor why, and would do it after
    the transcript had already left the machine, with nowhere to record that
    it had.
    """
    transport = install(monkeypatch)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "m")
    get_settings.cache_clear()
    _, _, context = _prepared(db_session)
    context.current_step_id = None  # prepare_run leaves it unset, execute_step sets it

    assert context.current_step_id is None
    with pytest.raises(StepPreconditionError, match="no running step"):
        BUILTIN_STEPS["summarize"](context)
    assert transport.calls == []
