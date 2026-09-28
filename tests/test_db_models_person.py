"""Tests for db.models.person.Person and db.models.user.User.

Two things this proves that a schema diff would not: a Segment can point
at a Person and read it back through the relationship, and a User can
point at a Person while both links stay optional: the shape meant
to give Segment.person_id, without forcing either side of it.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from voxtrama.db.models.person import Person
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.db.models.user import ROLE_OWNER, User


def _make_transcript(session: Session) -> Transcript:
    run = Run(workflow_name="demo", workflow_version="1.0.0", state=RunState.SUCCEEDED)
    transcript = Transcript(
        recording_id="rec1",
        language="it",
        model_name="whisper",
        model_revision="1",
        hardware_profile="cpu",
    )
    session.add_all([run, transcript])
    session.commit()
    return transcript


def test_a_segment_links_to_a_person_and_reads_it_back(db_session: Session) -> None:
    person = Person(given_name="Giulia", family_name="Verdi")
    transcript = _make_transcript(db_session)
    segment = Segment(
        transcript_id=transcript.id,
        start=0.0,
        end=1.0,
        text="ciao",
        confidence=0.9,
        person=person,
    )
    db_session.add_all([person, segment])
    db_session.commit()

    reloaded = db_session.get(Segment, segment.id)
    assert reloaded.person.given_name == "Giulia"


def test_a_segment_without_a_person_stays_that_way(db_session: Session) -> None:
    transcript = _make_transcript(db_session)
    segment = Segment(transcript_id=transcript.id, start=0.0, end=1.0, text="ciao", confidence=0.9)
    db_session.add(segment)
    db_session.commit()

    reloaded = db_session.get(Segment, segment.id)
    assert reloaded.person_id is None
    assert reloaded.person is None


def test_a_user_links_to_a_person_and_the_link_is_optional_both_ways(
    db_session: Session,
) -> None:
    person = Person(given_name="Marco", family_name="Rossi")
    linked_user = User(given_name="Marco", family_name="", role=ROLE_OWNER, person=person)
    unlinked_user = User(given_name="Nobody", family_name="", role=ROLE_OWNER)
    db_session.add_all([person, linked_user, unlinked_user])
    db_session.commit()

    assert db_session.get(User, linked_user.id).person.family_name == "Rossi"
    assert db_session.get(User, unlinked_user.id).person is None
