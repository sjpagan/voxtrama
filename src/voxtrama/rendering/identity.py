"""What an interior section's header shows for "who is this".

The identity shown top-right comes from the local
user's own name. db.people.local_user resolves it. This module decides
what the initials and the full name look like, the calculation that
stays out of the template.

**Two initials when there are two words, one when there is one.** The
earlier rule took a single character, to survive a one-word name, an
ideogram or a hyphen. The header wants the given and family initials. The
rule below satisfies both: the first letter of the given name, plus the
first letter of the family name when there is one. `"Owner"` (the name
migration 0011 seeds, and the only one any existing installation holds)
yields one letter, not a letter and an invented second.

The family initial comes from the **last** word of the family name, not
the second word of the whole name: "Anna Maria" / "De Luca" reads AL,
which is how that name is abbreviated, rather than AM.

Nothing here builds a fallback from an id or a role. A name not written
yet produces no initials, and the header shows no circle. rendering.runs
makes the same choice for a run with no recording: a blank is true and a
placeholder would not be.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from voxtrama.db.people import NoLocalUserError, local_user


@dataclass(frozen=True)
class Identity:
    """The local user's name as the header and the profile page show it."""

    given_name: str
    family_name: str
    initials: str

    @property
    def full_name(self) -> str:
        """Both parts with one space, or the given name alone when there is no family name."""
        return f"{self.given_name} {self.family_name}".strip()


def _initial(word: str) -> str:
    """The first character of `word`, uppercased where case exists.

    `str.upper()` on a CJK character is a no-op rather than an error, so
    this reads correctly for a name that has no notion of case.
    """
    stripped = word.strip()
    return stripped[0].upper() if stripped else ""


def read_identity(session: Session) -> Identity | None:
    """The local user's identity, or None when there is nothing honest to show.

    db.people.local_user raises NoLocalUserError when the `user` table
    does not hold exactly one row. A fully migrated installation never
    hits this, since migration 0011 seeds that one row.
    A database built straight from the ORM models, as the test fixtures
    do (Base.metadata.create_all, no migrations run), starts with none.
    That is normal for an unmigrated database, not a fault the header
    should raise 500 over.

    A user whose given name is blank returns None for the same reason:
    an identity with no name is not something to draw a circle around.
    """
    try:
        user = local_user(session)
    except NoLocalUserError:
        return None
    given, family = user.given_name.strip(), user.family_name.strip()
    if not given:
        return None
    family_words = family.split()
    family_initial = _initial(family_words[-1]) if family_words else ""
    return Identity(
        given_name=given, family_name=family, initials=f"{_initial(given)}{family_initial}"
    )


def header_initial(session: Session) -> str | None:
    """The initials the header's circle shows, or None when there is no name.

    Its own function because the header needs only this much, and a
    template handed the whole Identity would be one step away from
    deciding something about it.
    """
    identity = read_identity(session)
    return identity.initials if identity else None


def header_full_name(session: Session) -> str | None:
    """The full name the identity menu behind the circle shows, or
    None when there is no name.

    Same shape as header_initial, and for the same reason: the header
    needs only this much of Identity, not the dataclass itself.
    """
    identity = read_identity(session)
    return identity.full_name if identity else None
