"""Save a name for a diarised speaker, and apply it.

Adapter, not core, for the same reason db.people is: api.routes.
run_speaker_names is the one entrypoint that calls this, the same way it
is the CLI and the API routes that call db.people.local_user (that
module's own docstring). Restoring the same choice onto a *later*
Transcript once a Recording is reprocessed is a different moment:
diarization.speaker_names.reapply_known_speakers does that,
from inside the engine, reading the SpeakerName rows this module writes.

Naming a speaker never touches `speaker_label` itself (the diarisation
label survives every human decision made about it): only `person_id`, on
the SpeakerName row that makes the choice stick across a rerun, and on
every already-written Segment whose label matches. So a page already
open on this Recording's own transcript shows the new name the moment it
is reloaded, not only the next time diarisation runs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from voxtrama.db.models.person import Person
from voxtrama.db.models.speaker_name import ADDED_PREFIX, SpeakerName
from voxtrama.db.models.transcript import Segment, Transcript


@dataclass(frozen=True)
class SpeakerNameEntry:
    """One row of the "Name speakers" panel's own form, already parsed."""

    label: str
    given_name: str
    family_name: str


def _existing_mapping(session: Session, recording_id: str) -> dict[str, SpeakerName]:
    rows = session.scalars(
        select(SpeakerName).where(SpeakerName.recording_id == recording_id)
    ).all()
    return {row.speaker_label: row for row in rows}


def _apply_to_segments(session: Session, recording_id: str, label: str, person_id: str) -> None:
    """Every already-written Segment of `recording_id` whose label is `label`,
    across every Transcript the Recording ever produced, not only the one
    the run page currently open happens to show.

    A segment someone moved to another speaker by hand (db.segment_speaker)
    keeps that choice: only segments with no Person yet, or already
    this one, follow the label."""
    transcript_ids = session.scalars(
        select(Transcript.id).where(Transcript.recording_id == recording_id)
    ).all()
    if not transcript_ids:
        return
    segments = session.scalars(
        select(Segment).where(
            Segment.transcript_id.in_(transcript_ids),
            Segment.speaker_label == label,
            or_(Segment.person_id.is_(None), Segment.person_id == person_id),
        )
    ).all()
    for segment in segments:
        segment.person_id = person_id


def _upsert_person(
    session: Session, recording_id: str, existing: SpeakerName | None, entry: SpeakerNameEntry
) -> str:
    """The Person `entry` names: `existing`'s own Person, renamed, or a new
    one with its own new SpeakerName row."""
    if existing is not None:
        person = session.get(Person, existing.person_id)
        person.given_name = entry.given_name
        person.family_name = entry.family_name
        return person.id
    person = Person(
        id=str(uuid.uuid4()), given_name=entry.given_name, family_name=entry.family_name
    )
    session.add(person)
    session.add(
        SpeakerName(recording_id=recording_id, speaker_label=entry.label, person_id=person.id)
    )
    return person.id


def save_speaker_names(
    session: Session, recording_id: str, entries: list[SpeakerNameEntry]
) -> None:
    """Create or rename a Person for every named entry, and apply it to
    `recording_id`'s own Segments and to its SpeakerName mapping.

    An entry with no given_name is skipped rather than clearing an
    existing name. The panel's rule is opt-in per voice: leaving a
    speaker unnamed reads the same as never having opened the panel.
    """
    mapping = _existing_mapping(session, recording_id)
    for entry in entries:
        if not entry.given_name:
            continue
        person_id = _upsert_person(session, recording_id, mapping.get(entry.label), entry)
        _apply_to_segments(session, recording_id, entry.label, person_id)
    session.commit()


def recording_speakers(session: Session, recording_id: str) -> dict[str, tuple[str, str]]:
    """Label -> (person id, display name) of every speaker named on `recording_id`."""
    rows = session.execute(
        select(SpeakerName.speaker_label, Person)
        .join(Person, Person.id == SpeakerName.person_id)
        .where(SpeakerName.recording_id == recording_id)
    ).all()
    return {label: (p.id, f"{p.given_name} {p.family_name}".strip()) for label, p in rows}


def add_speaker(session: Session, recording_id: str, name: str) -> str:
    """A Person on `recording_id` with no voice of their own; returns their label."""
    taken = recording_speakers(session, recording_id)
    for label, (_, known) in taken.items():
        if known.lower() == name.lower():
            return label
    added = [int(label[1:]) for label in taken if label.startswith(ADDED_PREFIX)]
    label = f"{ADDED_PREFIX}{max(added, default=0) + 1}"
    given, _, family = name.partition(" ")
    person = Person(id=str(uuid.uuid4()), given_name=given, family_name=family)
    session.add(person)
    session.add(SpeakerName(recording_id=recording_id, speaker_label=label, person_id=person.id))
    session.commit()
    return label
