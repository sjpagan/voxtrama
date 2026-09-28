"""diarize's own run choice: the run's max_speakers wins over Settings.

Split from tests/test_engine_step_transcribe_provenance.py's own pattern
(create_run, prepare_run, execute_step), narrowed to the one field
engine.diarize_step.run_diarize now reads from RunChoices.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.models.step import StepState
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step, Workflow


def _workflow() -> Workflow:
    return Workflow(
        name="diarize-only",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="diarize", skill="diarize", skill_version="1.0.0")],
    )


def _spy_assign_speakers(calls: list[int | None]):
    def _fake(
        transcript,
        audio_path,
        models_dir,
        max_speakers=4,
        on_download=None,
        on_progress=None,
    ):
        calls.append(max_speakers)
        transcript.speaker_estimate = 1
        return transcript

    return _fake


def _no_op_reapply(session, recording_id, transcript) -> None:
    return None


def test_the_run_s_own_max_speakers_wins_over_settings(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_MAX_SPEAKERS", "4")
    get_settings.cache_clear()
    calls: list[int | None] = []
    monkeypatch.setattr("voxtrama.diarization.assign_speakers", _spy_assign_speakers(calls))
    monkeypatch.setattr("voxtrama.diarization.reapply_known_speakers", _no_op_reapply)
    run = create_run(db_session, "diarize-only", "unpinned", choices=RunChoices(max_speakers=2))
    step = Step(id="diarize", skill="diarize", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow())
    context.transcript = Transcript(
        recording_id="rec-1",
        language="en",
        model_name="whisper-fake",
        model_revision="rev-9",
        hardware_profile="low",
    )
    context.transcript.segments = [Segment(start=0.0, end=1.0, text="hi", confidence=1.0)]
    db_session.add(context.transcript)
    db_session.flush()
    context.audio_path = Path("does-not-matter.wav")

    execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)

    assert rows[0].state == StepState.SUCCEEDED
    assert calls == [2]


def test_a_run_that_chose_nothing_falls_back_to_settings_max_speakers(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_MAX_SPEAKERS", "6")
    get_settings.cache_clear()
    calls: list[int | None] = []
    monkeypatch.setattr("voxtrama.diarization.assign_speakers", _spy_assign_speakers(calls))
    monkeypatch.setattr("voxtrama.diarization.reapply_known_speakers", _no_op_reapply)
    run = create_run(db_session, "diarize-only", "unpinned")
    step = Step(id="diarize", skill="diarize", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow())
    context.transcript = Transcript(
        recording_id="rec-1",
        language="en",
        model_name="whisper-fake",
        model_revision="rev-9",
        hardware_profile="low",
    )
    context.transcript.segments = [Segment(start=0.0, end=1.0, text="hi", confidence=1.0)]
    db_session.add(context.transcript)
    db_session.flush()
    context.audio_path = Path("does-not-matter.wav")

    execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)

    assert calls == [6]
