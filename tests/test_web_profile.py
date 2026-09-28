"""The profile page: reading it, saving a name, and what
happens when the name saved is nothing at all.

These tests cover the round trip (the name typed into the form comes
back out of the identity circle) because that is the loop that did
not exist before: `given_name` was written once by migration 0011 and by
nobody else.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base, User
from voxtrama.db.models.user import ROLE_OWNER
from voxtrama.db.people import local_user


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    """A database holding one local user, the shape migration 0011 leaves."""
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(given_name="Owner", family_name="", role=ROLE_OWNER))
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine: Engine, tmp_path: Path) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def _stored(engine: Engine) -> tuple[str, str]:
    with Session(engine) as session:
        user = local_user(session)
        return user.given_name, user.family_name


def test_the_page_shows_the_name_already_stored(client: TestClient) -> None:
    body = client.get("/profile").text

    assert 'name="given_name"' in body
    assert 'value="Owner"' in body


def test_the_page_says_what_the_community_edition_lets_you_set(client: TestClient) -> None:
    """Two fields alone read as a form someone left unfinished; the page
    says in words that there is nothing else here.
    """
    assert "Community Edition" in client.get("/profile").text


def test_saving_a_name_changes_what_the_header_circle_shows(
    client: TestClient, engine: Engine
) -> None:
    posted = client.post(
        "/profile", data={"given_name": "Giorgio", "family_name": "Pagano"}, follow_redirects=False
    )

    assert posted.status_code == 303
    assert _stored(engine) == ("Giorgio", "Pagano")
    assert ">GP<" in client.get("/profile").text


def test_a_name_is_stripped_before_it_is_stored(client: TestClient, engine: Engine) -> None:
    client.post("/profile", data={"given_name": "  Giulia  ", "family_name": " "})

    assert _stored(engine) == ("Giulia", "")


def test_clearing_the_name_hides_the_circle_and_says_so(client: TestClient, engine: Engine) -> None:
    """Clearing your own name is allowed. The circle then disappears, and
    the page explains that as a consequence of what was typed rather than
    leaving it as a mystery.
    """
    client.post("/profile", data={"given_name": "", "family_name": ""})

    assert _stored(engine) == ("", "")
    body = client.get("/profile?saved=true").text
    assert "the circle at the top right is hidden" in body
    assert "vx-avatar" not in body


def test_the_menu_behind_the_circle_links_to_the_profile(client: TestClient) -> None:
    """ "Your profile" moved off the circle itself (the circle now
    opens a menu), but the link underneath still has to be a real one:
    focusable in reading order, openable in a new tab, reachable from the
    context menu, not a button pretending to navigate.
    """
    assert '<a href="/profile" class="vx-identity__link">' in client.get("/profile").text
