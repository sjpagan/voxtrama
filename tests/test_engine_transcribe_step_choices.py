"""transcribe's own run choice: cores_per_chunk/parallel_chunks win over Settings.

Split from tests/test_engine_step_transcribe_provenance.py's own pattern
(create_run, prepare_run, execute_step), narrowed to the two fields
engine.extractive_steps.run_transcribe now reads from RunChoices.
"""

from __future__ import annotations

import pytest
from fakes.machine import use_eight_cores
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import StepState
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step, Workflow


def _spy_transcribe(calls: list[tuple[int | None, int | None]]):
    def _fake(
        recording,
        hardware_profile,
        on_download=None,
        on_progress=None,
        cores_per_chunk=None,
        parallel_chunks=None,
        context=None,
        language=None,
    ):
        calls.append((cores_per_chunk, parallel_chunks))
        transcript = Transcript(
            recording_id=recording.id,
            language="en",
            model_name="whisper-fake",
            model_revision="rev-9",
            hardware_profile=hardware_profile,
        )
        transcript.segments = [Segment(start=0.0, end=1.0, text="hi", confidence=1.0)]
        return transcript

    return _fake


def _recording(session: Session) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=2.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def _workflow() -> Workflow:
    return Workflow(
        name="transcribe-only-choices",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="transcribe", skill="transcribe", skill_version="1.0.0")],
    )


def test_the_run_s_own_cores_and_parallel_chunks_win_over_settings(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_CORES_PER_CHUNK", "3")
    monkeypatch.setenv("VOXTRAMA_PARALLEL_CHUNKS", "2")
    use_eight_cores(monkeypatch)  # 7 cores asked must not be capped by a smaller host
    calls: list[tuple[int | None, int | None]] = []
    monkeypatch.setattr("voxtrama.transcription.transcribe", _spy_transcribe(calls))
    recording = _recording(db_session)
    choices = RunChoices(cores_per_chunk=7, parallel_chunks=1)
    run = create_run(
        db_session,
        "transcribe-only-choices",
        "unpinned",
        recording_id=recording.id,
        choices=choices,
    )
    step = Step(id="transcribe", skill="transcribe", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow())

    execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)

    assert rows[0].state == StepState.SUCCEEDED
    assert calls == [(7, 1)]


def test_a_run_that_chose_nothing_leaves_settings_to_transcribe_itself(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[int | None, int | None]] = []
    monkeypatch.setattr("voxtrama.transcription.transcribe", _spy_transcribe(calls))
    recording = _recording(db_session)
    run = create_run(db_session, "transcribe-only-choices", "unpinned", recording_id=recording.id)
    step = Step(id="transcribe", skill="transcribe", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow())

    execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)

    # None, None: run_transcribe hands over exactly what the run chose
    # (nothing), and transcribe() itself is the one place that falls that
    # back to Settings/tuning. This test only proves the engine did not
    # pre-resolve it a second time.
    assert calls == [(None, None)]
