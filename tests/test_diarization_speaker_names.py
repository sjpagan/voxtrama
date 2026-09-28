"""Tests for diarization.speaker_names.reapply_known_speakers.

The other half of test_db_speaker_naming.py: that module writes a
SpeakerName row when a human names a speaker, this one reads it back onto
a *later* Transcript's own fresh Segments: the moment a Recording is
reprocessed and diarisation produces new rows with no Person link of
their own yet.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from voxtrama.db.models.person import Person
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.speaker_name import SpeakerName
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.diarization.speaker_names import reapply_known_speakers


def _seed_known_speaker(session: Session, recording_id: str) -> str:
    session.add(
        Recording(
            id=recording_id,
            original_filename="clip.wav",
            stored_path="x",
            content_sha256="a" * 64,
            duration_seconds=10.0,
            media_format="wav",
        )
    )
    person = Person(id="p1", given_name="Sarah", family_name="")
    session.add(person)
    session.add(
        SpeakerName(id="sn1", recording_id=recording_id, speaker_label="spk0", person_id="p1")
    )
    session.commit()
    return person.id


def _fresh_transcript(recording_id: str) -> Transcript:
    transcript = Transcript(
        recording_id=recording_id,
        language="en",
        model_name="whisper",
        model_revision="v2",
        hardware_profile="cpu",
    )
    transcript.segments = [
        Segment(start=0.0, end=1.0, text="a", confidence=1.0, speaker_label="spk0"),
        Segment(start=1.0, end=2.0, text="b", confidence=1.0, speaker_label="spk1"),
    ]
    return transcript


def test_a_known_labels_person_is_restored_onto_the_new_segments(db_session: Session) -> None:
    person_id = _seed_known_speaker(db_session, "rec1")
    transcript = _fresh_transcript("rec1")

    reapply_known_speakers(db_session, "rec1", transcript)

    spk0 = next(s for s in transcript.segments if s.speaker_label == "spk0")
    spk1 = next(s for s in transcript.segments if s.speaker_label == "spk1")
    assert spk0.person_id == person_id
    assert spk1.person_id is None


def test_a_recording_nobody_ever_named_is_left_untouched(db_session: Session) -> None:
    db_session.add(
        Recording(
            id="rec2",
            original_filename="clip.wav",
            stored_path="x",
            content_sha256="b" * 64,
            duration_seconds=10.0,
            media_format="wav",
        )
    )
    db_session.commit()
    transcript = _fresh_transcript("rec2")

    reapply_known_speakers(db_session, "rec2", transcript)

    assert all(segment.person_id is None for segment in transcript.segments)
