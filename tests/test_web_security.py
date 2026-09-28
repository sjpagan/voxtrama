"""The app's own boundary, found missing by a security check.

Voxtrama has no login and listens on 127.0.0.1, and that address was the
whole boundary. Measured against a running instance:

- `/search?q="><script>...` put the script into the page, run as the app;
- a POST with `Origin: https://evil.example` changed the profile name,
  which every page then printed raw;
- a request with `Host: evil.example` was served (DNS rebinding).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base

SCRIPT = '"><script>alert(1)</script>'


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(f"sqlite:///{tmp_path / 'security.db'}")
    Base.metadata.create_all(engine)
    seed_local_user(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app, follow_redirects=False)


def test_a_search_never_puts_the_query_into_the_page_as_markup(client) -> None:
    body = client.get("/search", params={"q": SCRIPT}).text

    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


def test_a_name_with_markup_is_shown_as_text_on_every_page(client) -> None:
    client.post("/profile", data={"given_name": SCRIPT, "family_name": ""})

    body = client.get("/").text

    assert "<script>alert(1)</script>" not in body


def test_a_translation_written_as_html_is_not_escaped_twice(client) -> None:
    body = client.get("/setup").text

    assert "Data &amp; privacy" in body
    assert "&amp;amp;" not in body


def test_a_foreign_host_is_refused(client) -> None:
    assert client.get("/jobs", headers={"Host": "evil.example"}).status_code == 403
    assert client.get("/jobs", headers={"Host": "localhost:8000"}).status_code == 200
    assert client.get("/jobs", headers={"Host": "[::1]:8000"}).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ],
)
def test_a_change_asked_by_another_site_is_refused(client, headers) -> None:
    response = client.post("/profile", data={"given_name": "Mallory"}, headers=headers)

    assert response.status_code == 403
    assert "Mallory" not in client.get("/").text


def test_a_change_from_the_app_s_own_page_goes_through(client) -> None:
    headers = {"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"}

    response = client.post("/profile", data={"given_name": "Ada"}, headers=headers)

    assert response.status_code == 303


def test_a_client_that_sends_no_origin_is_not_a_browser_and_goes_through(client) -> None:
    """curl and the CLI send neither header; a browser always sends one on a POST."""
    assert client.post("/profile", data={"given_name": "Ada"}).status_code == 303


def test_every_response_carries_the_security_headers(client) -> None:
    for response in (client.get("/"), client.get("/jobs", headers={"Host": "evil.example"})):
        policy = response.headers["content-security-policy"]
        assert "script-src 'self'" in policy
        assert "frame-ancestors 'none'" in policy
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
