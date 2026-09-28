"""SQLAlchemy model for SpeakerName: a name pinned to one recording's own
speaker label, independently of any single Transcript.

Segment.person_id (db.models.transcript, migration 0011) is where a run's
own rendering reads a speaker's name from. This table is not a second
copy of that answer. It exists only so a name survives what Segment.
person_id cannot survive on its own: reprocessing a Recording writes a
new Transcript with new Segment rows, none of which carry any Person link
yet. diarization.speaker_names.reapply_known_speakers reads this table
once, right after a fresh diarisation labels those new Segments, and
writes person_id back onto the ones whose label was named before. That is
the only reason `speaker_label` is duplicated here instead of being looked up
through Segment.

Unique on (recording_id, speaker_label): naming `spk0` again for the same
Recording updates the existing row rather than creating a second one. The
unique constraint alone does not enforce that: the call site,
db.speaker_naming.save_speaker_names, upserts instead.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from voxtrama.db.models.run import Base

# A speaker added by hand has no voice of their own, so no diarisation
# label. Their row carries one of these instead: "+1", "+2"... Diarisation
# writes "spk0"-style labels, so the two never meet, and a rerun
# (diarization.speaker_names) has nothing to reapply them to.
ADDED_PREFIX = "+"


class SpeakerName(Base):
    """One (recording, speaker_label) pinned to a Person, by a human's own choice."""

    __tablename__ = "speaker_name"
    __table_args__ = (
        UniqueConstraint("recording_id", "speaker_label", name="uq_speaker_name_recording_label"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recording_id: Mapped[str] = mapped_column(String(36), ForeignKey("recording.id"))
    speaker_label: Mapped[str] = mapped_column(String(32))
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("person.id"))
