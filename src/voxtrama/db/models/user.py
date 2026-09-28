"""SQLAlchemy model for a User: whoever operates this installation.

The `local` profile has no authentication,
so Community Edition has exactly one User row, and this table exists to
give Run.created_by and Recording.created_by something to point at, not
to model a login, which nothing here checks. Migration 0011 inserts that
one row; see its docstring for why the migration is the right place and
not application startup.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voxtrama.db.models.person import Person
from voxtrama.db.models.run import Base

# The one role Community Edition knows. Other roles, and the checks that
# would use them, are left to Enterprise.
ROLE_OWNER = "owner"


class User(Base):
    """The local operator of this installation, linkable to a Person.

    person_id is nullable in both directions: the user does not
    have to say which speaker they are, and a Person does not become a
    User by being recorded.
    """

    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Two columns, not one composed string (migration 0017): the row is
    # meant to grow (the Enterprise edition puts more of a person on it), and a
    # single name would have to be split after the fact, guessing where one part
    # ends, on data nobody agreed to have parsed. Empty family_name is ordinary:
    # a one-word name is what every existing installation carries, seeded as
    # "Owner" by migration 0011.
    given_name: Mapped[str] = mapped_column(String)
    family_name: Mapped[str] = mapped_column(String)
    # The theme this person chose: light, dark, or auto (auto meaning
    # "follow the system"; migration 0018). On the user row and not in
    # the browser because it is a preference of the person, not of whichever
    # browser they opened today. rendering.theme reads it, and is also where
    # an unknown value falls back rather than raising.
    theme: Mapped[str] = mapped_column(String, default="auto", server_default="auto")
    role: Mapped[str] = mapped_column(String)
    person_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("person.id"), nullable=True
    )

    person: Mapped[Person | None] = relationship()
