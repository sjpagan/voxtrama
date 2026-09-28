"""db.segment_speaker: fixing the speaker of one sentence only."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.db.segment_speaker import assign_segments, speaker_choices
from voxtrama.db.speaker_naming import SpeakerNameEntry, save_speaker_names


def _seed(session: Session) -> list[str]:
    session.add(
        Recording(
            id="rec1",
            original_filename="clip.wav",
            stored_path="x",
            content_sha256="a" * 64,
            duration_seconds=10.0,
            media_format="wav",
        )
    )
    transcript = Transcript(
        id="t1",
        recording_id="rec1",
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="cpu",
    )
    transcript.segments = [
        Segment(start=0.0, end=1.0, text="a", confidence=1.0, speaker_label="spk0"),
        Segment(start=1.0, end=2.0, text="b", confidence=1.0, speaker_label="spk0"),
        Segment(start=2.0, end=3.0, text="c", confidence=1.0, speaker_label="spk1"),
    ]
    session.add(transcript)
    session.commit()
    save_speaker_names(
        session,
        "rec1",
        [
            SpeakerNameEntry(label="spk0", given_name="Alex", family_name=""),
            SpeakerNameEntry(label="spk1", given_name="Taylor", family_name=""),
        ],
    )
    return [s.id for s in session.scalars(select(Segment).order_by(Segment.start))]


def _names(session: Session) -> list[str | None]:
    segments = session.scalars(select(Segment).order_by(Segment.start))
    return [s.person.given_name if s.person else None for s in segments]


def test_one_sentence_moves_to_another_named_speaker(db_session: Session) -> None:
    ids = _seed(db_session)
    taylor = dict((name, pid) for pid, name in speaker_choices(db_session, "rec1"))["Taylor"]

    assign_segments(db_session, "rec1", [ids[1]], person_id=taylor)

    assert _names(db_session) == ["Alex", "Taylor", "Taylor"]
    labels = [s.speaker_label for s in db_session.scalars(select(Segment).order_by(Segment.start))]
    assert labels == ["spk0", "spk0", "spk1"]


def test_a_new_name_creates_one_person_and_reuses_it_after(db_session: Session) -> None:
    ids = _seed(db_session)

    assign_segments(db_session, "rec1", [ids[0]], new_name="Sam Rivera")
    assign_segments(db_session, "rec1", [ids[2]], new_name="sam rivera")

    assert _names(db_session) == ["Sam", "Alex", "Sam"]
    assert [name for _, name in speaker_choices(db_session, "rec1")] == [
        "Alex",
        "Sam Rivera",
        "Taylor",
    ]


def test_renaming_the_voice_keeps_a_sentence_fixed_by_hand(db_session: Session) -> None:
    ids = _seed(db_session)
    assign_segments(db_session, "rec1", [ids[1]], new_name="Sam")

    save_speaker_names(
        db_session, "rec1", [SpeakerNameEntry(label="spk0", given_name="Alexandra", family_name="")]
    )

    assert _names(db_session) == ["Alexandra", "Sam", "Taylor"]


def test_back_to_the_detected_speaker(db_session: Session) -> None:
    ids = _seed(db_session)
    assign_segments(db_session, "rec1", [ids[1]], new_name="Sam")

    assign_segments(db_session, "rec1", [ids[1]])

    assert _names(db_session) == ["Alex", "Alex", "Taylor"]


def test_segments_of_another_recording_are_left_alone(db_session: Session) -> None:
    _seed(db_session)

    assert assign_segments(db_session, "other", ["nope"], new_name="Sam") == 0
