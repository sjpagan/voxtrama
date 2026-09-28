"""transcribe's own provenance, isolated from summarize.

Split from test_engine_step_model_provenance.py to stay under the project's
size limit. Same fake transcribe, one narrower concern: `model` and
`model_revision` come from the Transcript this step itself produced, not
from a generative provider.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import StepState
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.workflow.definition import Step, Workflow


def _fake_transcribe(recording, hardware_profile, on_download=None, on_progress=None, **_ignored):
    """Stands in for transcription.asr.transcribe: no faster-whisper, no audio file."""
    transcript = Transcript(
        recording_id=recording.id,
        language="en",
        model_name="whisper-fake",
        model_revision="rev-9",
        hardware_profile=hardware_profile,
    )
    transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1.0)]
    return transcript


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
        name="transcribe-only",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="transcribe", skill="transcribe", skill_version="1.0.0")],
    )


def test_the_transcribe_step_writes_its_own_model_and_revision_onto_its_row(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voxtrama.transcription.transcribe", _fake_transcribe)
    recording = _recording(db_session)
    run = create_run(db_session, "transcribe-only", "unpinned", recording_id=recording.id)
    step = Step(id="transcribe", skill="transcribe", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow())

    execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)

    assert rows[0].state == StepState.SUCCEEDED
    assert rows[0].model == "whisper-fake"
    assert rows[0].model_revision == "rev-9"
    assert rows[0].provider == "local"
    assert rows[0].host is None
    assert rows[0].profile_check_skipped is False
    assert context.transcript is not None
    assert context.transcript.produced_by_run_id == run.id
    assert context.transcript.produced_by_step_id == "transcribe"
