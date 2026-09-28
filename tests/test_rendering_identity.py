"""Tests for rendering.identity.

The rule under test is "two initials when there are two names, one when
there is one", so the cases that matter are the ones where a rule built
for two words meets a name that does not have them.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.db.models import Base, User
from voxtrama.db.models.user import ROLE_OWNER
from voxtrama.rendering.identity import header_initial, read_identity


def _only_user(session: Session, given: str, family: str) -> None:
    session.query(User).delete()
    session.add(User(given_name=given, family_name=family, role=ROLE_OWNER))
    session.commit()


def test_the_seeded_local_user_gives_one_letter(db_session: Session) -> None:
    # conftest seeds "Owner" with no family name, the same one-word value
    # migration 0011 inserts and migration 0017 carries over: one letter,
    # not a letter plus an invented second.
    assert header_initial(db_session) == "O"


def test_a_given_and_family_name_give_two_letters(db_session: Session) -> None:
    _only_user(db_session, "Giorgio", "Pagano")

    assert header_initial(db_session) == "GP"


def test_a_one_word_name_gives_one_letter(db_session: Session) -> None:
    _only_user(db_session, "Madonna", "")

    assert header_initial(db_session) == "M"


def test_a_multi_word_family_name_uses_its_last_word(db_session: Session) -> None:
    """ "Anna Maria De Luca" is abbreviated AL, not AM: the family initial
    comes from the last word of the family name, not the second word of
    the whole name.
    """
    _only_user(db_session, "Anna Maria", "De Luca")

    assert header_initial(db_session) == "AL"


def test_an_accented_name_keeps_its_accent(db_session: Session) -> None:
    _only_user(db_session, "Élise", "Dupont")

    assert header_initial(db_session) == "ÉD"


def test_an_ideogram_name_is_its_own_initial(db_session: Session) -> None:
    """str.upper() on a CJK character is a no-op, not an error."""
    _only_user(db_session, "田中", "太郎")

    assert header_initial(db_session) == "田太"


def test_a_blank_name_shows_no_identity(db_session: Session) -> None:
    """Nobody has written a name yet: no circle, rather than a circle
    around nothing or a letter invented from the row's id.
    """
    _only_user(db_session, "   ", "")

    assert header_initial(db_session) is None
    assert read_identity(db_session) is None


def test_the_full_name_joins_both_parts_without_a_trailing_space(db_session: Session) -> None:
    _only_user(db_session, "Madonna", "")
    assert read_identity(db_session).full_name == "Madonna"

    _only_user(db_session, "Giorgio", "Pagano")
    assert read_identity(db_session).full_name == "Giorgio Pagano"


def test_a_database_with_no_local_user_yet_shows_no_identity() -> None:
    """The normal shape of a schema nobody has migrated (the module's own
    docstring), not a 500: a fresh Base.metadata.create_all() with no
    migration 0011 ever run against it, the same shape several of this
    project's own web test fixtures build.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert header_initial(session) is None
