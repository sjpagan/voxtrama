"""Tests for workflow.condition (the grammar) and engine.condition (evaluating it).

Not eval, on purpose (see workflow.condition's own docstring): these tests
exercise the one shape the grammar recognises, and confirm everything
outside it is rejected rather than half-understood.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.condition import ConditionEvaluationError, evaluate_condition
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.workflow.condition import ConditionSyntaxError, parse_condition


def _context(session: Session) -> ExecutionContext:
    run = create_run(session, "test-workflow", "unpinned")
    return ExecutionContext(session=session, run=run)


def _row(step_id: str, state: StepState) -> RunStep:
    return RunStep(
        run_id="a-run",
        step_id=step_id,
        skill="a-skill",
        skill_version="1.0.0",
        state=state,
        position=0,
    )


@pytest.mark.parametrize(
    "raw",
    [
        "recording.duration_seconds > 60",
        'transcript.language == "en"',
        'recording.media_type in ["audio/wav", "audio/mpeg"]',
        "steps.transcribe.speaker_estimate >= 2",
        'steps.transcribe.language not in ["en", "it"]',
    ],
)
def test_a_well_formed_condition_parses(raw: str) -> None:
    condition = parse_condition(raw)
    assert condition.raw == raw


@pytest.mark.parametrize(
    "raw",
    [
        "recording.duration_seconds",
        "recording.nonsense > 1",
        "recording.duration_seconds ~= 1",
        "recording.duration_seconds > not-json",
    ],
)
def test_a_malformed_condition_is_rejected(raw: str) -> None:
    with pytest.raises(ConditionSyntaxError):
        parse_condition(raw)


def test_evaluate_reads_the_recording(db_session: Session) -> None:
    context = _context(db_session)
    context.recording = Recording(
        original_filename="a.wav",
        stored_path="recordings/a.wav",
        content_sha256="0" * 64,
        duration_seconds=120.0,
        media_format="wav",
    )
    assert evaluate_condition(parse_condition("recording.duration_seconds > 60"), context)
    assert not evaluate_condition(parse_condition("recording.duration_seconds > 6000"), context)


def test_evaluate_reads_what_an_earlier_step_produced(db_session: Session) -> None:
    context = _context(db_session)
    context.produced["transcribe"] = {"transcript_id": "abc"}
    condition = parse_condition('steps.transcribe.transcript_id == "abc"')
    assert evaluate_condition(condition, context)


def test_evaluate_raises_when_the_referenced_step_never_produced_anything(
    db_session: Session,
) -> None:
    context = _context(db_session)
    condition = parse_condition('steps.transcribe.transcript_id == "abc"')
    with pytest.raises(ConditionEvaluationError):
        evaluate_condition(condition, context)


@pytest.mark.parametrize("state", [StepState.SUCCEEDED, StepState.FAILED, StepState.SKIPPED])
def test_evaluate_reads_a_step_s_final_state_even_when_it_produced_nothing(
    db_session: Session, state: StepState
) -> None:
    """A failed step never reaches context.produced. State must resolve anyway."""
    context = _context(db_session)
    context.step_rows["extract"] = _row("extract", state)
    condition = parse_condition(f'steps.extract.state == "{state.value}"')
    assert evaluate_condition(condition, context)


@pytest.mark.parametrize("state", [StepState.PENDING, StepState.RUNNING])
def test_evaluate_raises_when_the_referenced_step_has_not_finished_yet(
    db_session: Session, state: StepState
) -> None:
    context = _context(db_session)
    context.step_rows["extract"] = _row("extract", state)
    condition = parse_condition('steps.extract.state == "succeeded"')
    with pytest.raises(ConditionEvaluationError):
        evaluate_condition(condition, context)
