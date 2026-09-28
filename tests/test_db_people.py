"""Tests for db.people: the local user, and id-to-name resolution."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from voxtrama.db.models.person import Person
from voxtrama.db.models.user import ROLE_OWNER, User
from voxtrama.db.people import NoLocalUserError, local_user, resolve_person_names


def test_local_user_returns_the_one_row(db_session: Session) -> None:
    # db_session already seeds one owner (tests/conftest.py, matching
    # migration 0011): this proves local_user() finds exactly that row.
    user = local_user(db_session)
    assert user.role == ROLE_OWNER


def test_local_user_raises_when_there_is_none(db_session: Session) -> None:
    db_session.query(User).delete()
    db_session.commit()

    with pytest.raises(NoLocalUserError):
        local_user(db_session)


def test_local_user_raises_when_there_is_more_than_one(db_session: Session) -> None:
    db_session.add(User(given_name="Second", family_name="", role=ROLE_OWNER))
    db_session.commit()

    with pytest.raises(NoLocalUserError):
        local_user(db_session)


def test_resolve_person_names_maps_known_ids_to_given_and_family_name(
    db_session: Session,
) -> None:
    person = Person(given_name="Giulia", family_name="Verdi")
    db_session.add(person)
    db_session.commit()

    names = resolve_person_names(db_session, [person.id])

    assert names == {person.id: "Giulia Verdi"}


def test_resolve_person_names_of_a_one_word_name_has_no_trailing_space(
    db_session: Session,
) -> None:
    # given_name/family_name are non-nullable, not non-empty: many people
    # have one name, and family_name="" must not become "Cher ".
    person = Person(given_name="Cher", family_name="")
    db_session.add(person)
    db_session.commit()

    names = resolve_person_names(db_session, [person.id])

    assert names == {person.id: "Cher"}


def test_resolve_person_names_omits_ids_with_no_matching_person(db_session: Session) -> None:
    names = resolve_person_names(db_session, ["not-a-real-id"])

    assert names == {}


def test_resolve_person_names_of_an_empty_iterable_is_an_empty_dict(db_session: Session) -> None:
    assert resolve_person_names(db_session, []) == {}
