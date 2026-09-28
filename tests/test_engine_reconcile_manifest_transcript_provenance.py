"""engine.reconcile_manifest.recording_and_transcript resolves by run, not recency.

Before migration 0014, a Transcript carried no run_id of its own, so this
function's only choice was the most recently created row of the
Recording. Re-transcribing the same Recording made an older run's
reconciliation pick up the newer Transcript, whose segments its own
evidence had never anchored to. These tests prove the fix, and that the
old guess still runs for rows written before migration 0014.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Transcript
from voxtrama.engine.reconcile_manifest import recording_and_transcript


def _recording(session: Session) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=42.0,
        media_format="wav",
    )
    session.add(recording)
    session.commit()
    return recording


def _run(session: Session, recording_id: str) -> Run:
    run = Run(
        workflow_name="transcribe-only",
        workflow_version="1.0.0",
        state=RunState.RUNNING,
        recording_id=recording_id,
    )
    session.add(run)
    session.commit()
    return run


def _transcript(
    session: Session,
    recording_id: str,
    *,
    created_at: datetime,
    produced_by_run_id: str | None,
) -> Transcript:
    transcript = Transcript(
        recording_id=recording_id,
        language="en",
        model_name="whisper-test",
        model_revision="rev-1",
        hardware_profile="cpu",
        created_at=created_at,
        produced_by_run_id=produced_by_run_id,
    )
    session.add(transcript)
    session.commit()
    return transcript


def test_reconciliation_resolves_the_transcript_its_own_run_produced(db_session: Session) -> None:
    recording = _recording(db_session)
    old_run = _run(db_session, recording.id)
    new_run = _run(db_session, recording.id)
    old_transcript = _transcript(
        db_session,
        recording.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        produced_by_run_id=old_run.id,
    )
    _transcript(
        db_session,
        recording.id,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
        produced_by_run_id=new_run.id,
    )

    _, transcript = recording_and_transcript(db_session, old_run)

    assert transcript is not None
    assert transcript.id == old_transcript.id


def test_a_transcript_with_no_producing_run_falls_back_to_the_most_recent(
    db_session: Session,
) -> None:
    """Rows written before migration 0014 have no produced_by_run_id to match on."""
    recording = _recording(db_session)
    run = _run(db_session, recording.id)
    _transcript(
        db_session,
        recording.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        produced_by_run_id=None,
    )
    newest = _transcript(
        db_session,
        recording.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=1),
        produced_by_run_id=None,
    )

    _, transcript = recording_and_transcript(db_session, run)

    assert transcript is not None
    assert transcript.id == newest.id


def test_a_retried_transcribe_resolves_the_attempt_the_run_carried_forward(
    db_session: Session,
) -> None:
    """An extractive step may be retried, and each attempt writes its own row."""
    recording = _recording(db_session)
    run = _run(db_session, recording.id)
    _transcript(
        db_session,
        recording.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        produced_by_run_id=run.id,
    )
    second_attempt = _transcript(
        db_session,
        recording.id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=3),
        produced_by_run_id=run.id,
    )

    _, transcript = recording_and_transcript(db_session, run)

    assert transcript is not None
    assert transcript.id == second_attempt.id
