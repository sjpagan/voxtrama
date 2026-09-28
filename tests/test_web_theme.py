"""Choosing a theme.

The three things this feature gets wrong elsewhere, each with a test:
"auto" written into the attribute (which silently disables the system
preference), the choice not surviving a reload, and the control sending
you back to the home page from wherever you used it.
"""

from __future__ import annotations

import re
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
from voxtrama.rendering.theme import Theme, attribute, stored_theme, theme_choices


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(given_name="Owner", family_name="", role=ROLE_OWNER, theme="auto"))
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


def test_auto_writes_no_attribute_at_all() -> None:
    """The bug that makes this feature silently useless: an attribute
    spelling "auto" matches no CSS rule, so the page stays on the
    unconditional default whatever the system says. Absent is the
    mechanism, not an optimisation.
    """
    assert attribute(Theme.AUTO) is None
    assert attribute(Theme.LIGHT) == "light"
    assert attribute(Theme.DARK) == "dark"


def test_the_default_installation_follows_the_system(client: TestClient) -> None:
    body = client.get("/").text

    assert "data-theme" not in body


def test_choosing_dark_renders_the_attribute_in_the_document(client: TestClient) -> None:
    client.post("/theme", data={"theme": "dark", "origin": "/"})

    assert 'data-theme="dark"' in client.get("/").text


def test_the_choice_survives_a_fresh_read_of_the_database(
    client: TestClient, engine: Engine
) -> None:
    """Stored on the user row, not in a browser: a second reader sees it."""
    client.post("/theme", data={"theme": "light", "origin": "/"})

    with Session(engine) as session:
        assert stored_theme(session) is Theme.LIGHT


def test_the_control_returns_to_the_page_it_was_used_from(client: TestClient) -> None:
    """A control present on every page that moves you elsewhere each time
    is worse than no control.
    """
    response = client.post(
        "/theme", data={"theme": "dark", "origin": "/profile"}, follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/profile"


def test_an_origin_pointing_off_site_is_refused(client: TestClient) -> None:
    """ "//evil.example" is a valid protocol-relative URL, not a path on
    this app: trusting it turns "go back where you were" into an open
    redirect.
    """
    response = client.post(
        "/theme", data={"theme": "dark", "origin": "//evil.example"}, follow_redirects=False
    )

    assert response.headers["location"] == "/"


def test_an_unknown_theme_falls_back_instead_of_failing(client: TestClient, engine: Engine) -> None:
    client.post("/theme", data={"theme": "sepia", "origin": "/"})

    with Session(engine) as session:
        assert stored_theme(session) is Theme.AUTO


def _option_tag(body: str, value: str) -> str:
    """The <button ...> opening tag for one theme value, attributes and all."""
    match = re.search(rf'value="{value}".*?>', body, re.S)
    assert match, f"no theme option for {value!r} in body"
    return match.group(0)


def test_the_control_names_the_active_state(client: TestClient) -> None:
    """ "Auto" on a dark system looks identical to "Dark": aria-current on
    the active option is the only thing that tells them apart, since the
    control moved out of its own summary and into the identity menu.
    """
    body = client.get("/").text
    assert "aria-current" in _option_tag(body, "auto")

    client.post("/theme", data={"theme": "light", "origin": "/"})
    body = client.get("/").text
    assert "aria-current" in _option_tag(body, "light")
    assert "aria-current" not in _option_tag(body, "auto")


def test_exactly_one_choice_is_marked_current(client: TestClient) -> None:
    choices = theme_choices(Theme.DARK)

    assert [choice.value for choice in choices if choice.active] == [Theme.DARK]
    assert len(choices) == 3
