"""GET /'s sidebar and identity circle.

Split from test_shell_route.py, which covers the shell's plumbing
(stylesheet links, no external URL, locale negotiation), so neither file
grows past the project's size limit. Before this, the home route passed
neither `nav_items` nor `user_initial` at all, so `.vx-avatar` and
`.vx-sidebar` were always absent from `/`, the only page with no way
back to /profile except typing the URL.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base, User
from voxtrama.db.models.user import ROLE_OWNER


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """A real app against an empty, migrated-shape database (GET / now reads one)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app)


def test_root_renders_the_sidebar(client: TestClient) -> None:
    """The home page is a section like any other now, not the one
    place with nowhere to navigate to.
    """
    body = client.get("/").text
    assert '<aside class="vx-sidebar"' in body


def test_root_marks_home_as_the_current_sidebar_section(client: TestClient) -> None:
    """The home (the new-job form) has its own entry, Home,
    marked active here; Jobs leads to /jobs. The brand leads home too.
    """
    body = client.get("/").text
    assert '<a href="/" aria-current="page">' in body
    assert '<a class="vx-brand" href="/"' in body


def test_root_renders_the_identity_circle_when_a_name_is_written(
    tmp_path: Path, client: TestClient
) -> None:
    """The defect this test covers: `.vx-avatar` was always null on `/`,
    because the route never reached page_context's user_initial at all
    (see header.html's own `{% if user_initial %}`).
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    with Session(engine) as session:
        session.add(User(given_name="Giorgio", family_name="Pagano", role=ROLE_OWNER))
        session.commit()
    engine.dispose()

    body = client.get("/").text

    assert '<span class="vx-avatar" aria-hidden="true">GP</span>' in body


def test_root_identity_menu_shows_the_full_name(tmp_path: Path, client: TestClient) -> None:
    """The circle alone only ever showed two initials. The menu
    behind it is where page_context's user_full_name is spent.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    with Session(engine) as session:
        session.add(User(given_name="Giorgio", family_name="Pagano", role=ROLE_OWNER))
        session.commit()
    engine.dispose()

    body = client.get("/").text

    assert '<p class="vx-identity__name">Giorgio Pagano</p>' in body


def test_root_has_no_identity_circle_when_no_name_is_written(client: TestClient) -> None:
    """No User row (the fixture's own empty database) means no name yet:
    the same "no circle" rule rendering.identity already applies elsewhere.
    """
    body = client.get("/").text
    assert "vx-avatar" not in body
