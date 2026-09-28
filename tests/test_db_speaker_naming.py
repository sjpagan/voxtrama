"""Tests for db.speaker_naming.save_speaker_names.

db_session (tests/conftest.py) is an in-memory SQLite session with the
schema already created and the one User migration 0011 seeds. This
module needs neither, only Recording/Transcript/Segment/Person/
SpeakerName, all reachable straight off the same session.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.person import Person
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.speaker_name import SpeakerName
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.db.speaker_naming import SpeakerNameEntry, save_speaker_names


def _seed_recording_with_two_speakers(session: Session, recording_id: str) -> None:
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
    transcript = Transcript(
        id=f"t-{recording_id}",
        recording_id=recording_id,
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="cpu",
    )
    transcript.segments = [
        Segment(start=0.0, end=1.0, text="a", confidence=1.0, speaker_label="spk0"),
        Segment(start=1.0, end=2.0, text="b", confidence=1.0, speaker_label="spk1"),
    ]
    session.add(transcript)
    session.commit()


def test_naming_a_speaker_creates_a_person_and_links_its_segments(db_session: Session) -> None:
    _seed_recording_with_two_speakers(db_session, "rec1")

    save_speaker_names(
        db_session,
        "rec1",
        [SpeakerNameEntry(label="spk0", given_name="Sarah", family_name="Connor")],
    )

    named = db_session.scalars(select(Segment).where(Segment.speaker_label == "spk0")).one()
    other = db_session.scalars(select(Segment).where(Segment.speaker_label == "spk1")).one()
    assert named.person.given_name == "Sarah"
    assert named.person.family_name == "Connor"
    assert other.person_id is None


def test_a_speaker_left_blank_is_not_touched(db_session: Session) -> None:
    _seed_recording_with_two_speakers(db_session, "rec2")

    save_speaker_names(
        db_session,
        "rec2",
        [
            SpeakerNameEntry(label="spk0", given_name="Sarah", family_name=""),
            SpeakerNameEntry(label="spk1", given_name="", family_name=""),
        ],
    )

    spk1 = db_session.scalars(select(Segment).where(Segment.speaker_label == "spk1")).one()
    assert spk1.person_id is None


def test_saving_twice_renames_the_same_person_instead_of_creating_a_second_one(
    db_session: Session,
) -> None:
    _seed_recording_with_two_speakers(db_session, "rec3")
    save_speaker_names(
        db_session, "rec3", [SpeakerNameEntry(label="spk0", given_name="Sarah", family_name="")]
    )
    first_person_id = (
        db_session.scalars(select(Segment).where(Segment.speaker_label == "spk0")).one().person_id
    )

    save_speaker_names(
        db_session, "rec3", [SpeakerNameEntry(label="spk0", given_name="Sally", family_name="")]
    )

    segment = db_session.scalars(select(Segment).where(Segment.speaker_label == "spk0")).one()
    assert segment.person_id == first_person_id
    assert segment.person.given_name == "Sally"
    assert db_session.scalars(select(Person)).all().__len__() == 1


def test_a_speaker_name_row_is_written_for_reprocessing_to_find_later(
    db_session: Session,
) -> None:
    _seed_recording_with_two_speakers(db_session, "rec4")

    save_speaker_names(
        db_session, "rec4", [SpeakerNameEntry(label="spk0", given_name="Sarah", family_name="")]
    )

    row = db_session.scalars(
        select(SpeakerName).where(
            SpeakerName.recording_id == "rec4", SpeakerName.speaker_label == "spk0"
        )
    ).one()
    person = db_session.get(Person, row.person_id)
    assert person.given_name == "Sarah"
