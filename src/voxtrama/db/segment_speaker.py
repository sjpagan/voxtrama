"""Correct the speaker of single sentences: "the name is wrong on
this line only".

"Name speakers" (db.speaker_naming) names a whole voice: every segment
diarisation gave the same label. When diarisation got one sentence wrong,
that sentence belongs to someone else while the rest of its label stays
right. This moves the chosen segments alone, by setting their own
`person_id`. `speaker_label` is never touched, so what the
machine heard stays on record beside what a person decided.

The names offered are the people already named on this recording. A new
name reuses a Person of this recording with the same name before creating
one. "Back to the detected speaker" clears the choice: the segment
follows its label again, named or not. Adapter, not core, like
db.speaker_naming: only an API route calls it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.person import Person
from voxtrama.db.models.speaker_name import SpeakerName
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.db.people import resolve_person_names


def _segments_of(session: Session, recording_id: str) -> list[Segment]:
    transcript_ids = select(Transcript.id).where(Transcript.recording_id == recording_id)
    return list(session.scalars(select(Segment).where(Segment.transcript_id.in_(transcript_ids))))


def speaker_choices(session: Session, recording_id: str) -> list[tuple[str, str]]:
    """(person id, name) of everyone already named on `recording_id`, by name."""
    ids = {segment.person_id for segment in _segments_of(session, recording_id)}
    named = select(SpeakerName.person_id).where(SpeakerName.recording_id == recording_id)
    ids |= set(session.scalars(named))
    names = resolve_person_names(session, {person_id for person_id in ids if person_id})
    return sorted(names.items(), key=lambda item: item[1].lower())


def _person_for(session: Session, recording_id: str, name: str) -> str:
    """The Person of this recording called `name`, or a new one."""
    for person_id, known in speaker_choices(session, recording_id):
        if known.lower() == name.lower():
            return person_id
    given, _, family = name.partition(" ")
    person = Person(id=str(uuid.uuid4()), given_name=given, family_name=family)
    session.add(person)
    return person.id


def _label_person(session: Session, recording_id: str, label: str | None) -> str | None:
    if label is None:
        return None
    return session.scalar(
        select(SpeakerName.person_id).where(
            SpeakerName.recording_id == recording_id, SpeakerName.speaker_label == label
        )
    )


def assign_segments(
    session: Session,
    recording_id: str,
    segment_ids: list[str],
    person_id: str | None = None,
    new_name: str = "",
) -> int:
    """Give `segment_ids` (only those of `recording_id`) one speaker.

    `new_name` wins over `person_id`; with neither, the segments go back to
    whatever their own label is named. Returns how many segments changed.
    """
    wanted = set(segment_ids)
    segments = [s for s in _segments_of(session, recording_id) if s.id in wanted]
    target = person_id
    if new_name.strip():
        target = _person_for(session, recording_id, new_name.strip())
    for segment in segments:
        segment.person_id = target or _label_person(session, recording_id, segment.speaker_label)
    session.commit()
    return len(segments)
