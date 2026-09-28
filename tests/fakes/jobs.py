"""Jobs with a recording and a transcript, for the Jobs page and search tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Segment, Transcript


def seed_job(
    session: Session,
    data_dir: Path,
    label: str,
    lines: list[str],
    state: RunState = RunState.SUCCEEDED,
    day: int = 1,
) -> Run:
    """A finished job: recording files on disk, a run, output.json, a transcript."""
    recording = Recording(
        original_filename=f"{label}.wav",
        stored_path="",
        content_sha256="0" * 64,
        duration_seconds=125.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    folder = data_dir / "recordings" / recording.id
    folder.mkdir(parents=True)
    (folder / "audio.wav").write_bytes(b"RIFF")
    recording.stored_path = f"recordings/{recording.id}/audio.wav"
    run = Run(
        workflow_name="meeting-decisions",
        workflow_version="1.0.0",
        state=state,
        recording_id=recording.id,
        label=label,
        created_at=datetime(2026, 9, day, tzinfo=UTC),
    )
    session.add(run)
    session.flush()
    (data_dir / "runs" / run.id).mkdir(parents=True)
    (data_dir / "runs" / run.id / "output.json").write_text("{}")
    session.add(_transcript(recording.id, run.id, lines))
    session.commit()
    return run


def _transcript(recording_id: str, run_id: str, lines: list[str]) -> Transcript:
    transcript = Transcript(
        recording_id=recording_id,
        language="en",
        model_name="small",
        model_revision="r",
        hardware_profile="low",
        produced_by_run_id=run_id,
    )
    transcript.segments = [
        Segment(start=10.0 * i, end=10.0 * i + 5, text=text, confidence=1.0, speaker_label="spk0")
        for i, text in enumerate(lines)
    ]
    return transcript
