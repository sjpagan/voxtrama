"""A run that chose to skip diarize really skips it.

Drives the choice through execute_run, the way test_engine_run_choices.py
does for step_skills, and reads back both the RunStep rows and the
manifest. engine.diarize_choice's own rules are covered in isolation by
tests/test_engine_diarize_choice.py.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import RunStep
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step, Workflow


def _fake_transcribe(recording, hardware_profile, on_download=None, on_progress=None, **kwargs):
    """Stands in for transcription.asr.transcribe: no faster-whisper, no audio file."""
    transcript = Transcript(
        recording_id=recording.id,
        language="en",
        model_name="whisper-fake",
        model_revision="rev-9",
        hardware_profile=hardware_profile,
    )
    transcript.segments = [Segment(start=0.0, end=1.0, text="hi", confidence=1.0)]
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
        name="transcribe-and-diarize",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[
            Step(id="transcribe", skill="transcribe", skill_version="1.0.0"),
            Step(id="diarize", skill="diarize", skill_version="1.0.0", depends_on=["transcribe"]),
        ],
    )


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def test_a_run_that_declines_diarize_never_runs_or_plans_it(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voxtrama.transcription.transcribe", _fake_transcribe)
    recording = _recording(db_session)
    choices = RunChoices(diarize=False)
    created = create_run(
        db_session,
        "transcribe-and-diarize",
        "unpinned",
        recording_id=recording.id,
        choices=choices,
    )

    run = execute_run(db_session, created.id, workflow=_workflow())

    step_ids = db_session.scalars(select(RunStep.step_id).where(RunStep.run_id == run.id)).all()
    assert step_ids == ["transcribe"]

    manifest = _read_manifest(run.id)
    assert [step.step_id for step in manifest.steps] == ["transcribe"]
    assert manifest.choices.diarize is False
