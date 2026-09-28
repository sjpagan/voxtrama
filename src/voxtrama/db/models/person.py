"""SQLAlchemy model for a Person: someone captured by a recording.

Person is kept apart from User: a Person is a voice in a Segment, a
colleague, a client, an interviewee: almost never whoever operates
Voxtrama. No email, no other field: Enterprise gets "the seam, not the
columns", so Community stores only what naming a speaker
needs.
"""

from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from voxtrama.db.models.run import Base


class Person(Base):
    """Someone a Segment's speaker_label was linked to by hand.

    The link itself lives on Segment.person_id, added by migration 0011
    alongside this table. Person did not exist for the seven issues that
    came before it, which is why Segment.person_id started out without a
    ForeignKey.
    """

    __tablename__ = "person"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    given_name: Mapped[str] = mapped_column(String)
    family_name: Mapped[str] = mapped_column(String)
