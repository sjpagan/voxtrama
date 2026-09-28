"""Query layer for Person and User: the local user, and id-to-name resolution.

Adapter, not core (tests/test_architecture.py classifies `db` this way,
while db.models, where Person and User live, is core). engine
cannot import this: `created_by` is passed into engine.enqueue.enqueue_run
and ingest.local_file.import_local_file rather than looked up there, and
it is the CLI and the API routes (both entrypoints) that call
local_user() here and pass its id on.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.person import Person
from voxtrama.db.models.user import User


class NoLocalUserError(RuntimeError):
    """Raised when the `user` table does not hold exactly one row.

    Community Edition has one User, created at first
    startup. Migration 0011 inserts that one row and nothing removes
    it. Zero or several rows means a database that does not match its
    own migrations. Returning None here would let that surface three
    calls later, as a puzzling AttributeError instead of this.
    """


def local_user(session: Session) -> User:
    """Return the Community Edition's one local user, or raise.

    There is no authentication to resolve instead: the
    `local` profile has exactly one user, so finding it never needs an id.
    """
    users = session.scalars(select(User)).all()
    if len(users) != 1:
        raise NoLocalUserError(f"expected exactly one user, found {len(users)}")
    return users[0]


def _display_name(person: Person) -> str:
    """The "given family" name, or whichever half exists, never a trailing space.

    given_name and family_name are non-nullable, but not non-empty: many
    people have one name, not two, and a blank family_name is a value the
    columns allow. Joining only the non-empty parts is a decision about
    what a name is, not formatting: a bare f-string would put a space
    after "Giulia" that ends up on someone's screen.
    """
    return " ".join(part for part in (person.given_name, person.family_name) if part)


def resolve_person_names(session: Session, person_ids: Iterable[str]) -> dict[str, str]:
    """Map each id in `person_ids` to its Person's display name.

    An id with no matching Person is left out of the result rather than
    mapped to a placeholder: whoever renders a speaker (not this layer)
    decides what to show in its place.
    """
    ids = list(person_ids)
    if not ids:
        return {}
    people = session.scalars(select(Person).where(Person.id.in_(ids))).all()
    return {person.id: _display_name(person) for person in people}
