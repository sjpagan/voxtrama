"""HTTP tests for GET / and the /static mount it depends on.

tests/test_web_shell.py already proves base.html itself is well-formed
(stylesheet order, no CDN hosts, the compiled CSS exists) by rendering it
straight off disk with a throwaway Environment; the plumbing that
gets it to a browser is wired now, and GET / has a Runs list, so it now
reads the database too. These tests exercise that through the real app.
tests/test_shell_runs_list.py covers what the list itself shows;
tests/test_shell_identity.py covers the sidebar and the identity circle.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.catalog import write_catalog
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.api.routes import shell as shell_route
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.i18n import catalogs

_EXTERNAL_URL = re.compile(r'(?:href|src)\s*=\s*"(https?://[^"]+)"')

_EMPTY_ITALIAN_PO = """
msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"
"""


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


def test_root_renders_the_base_html_shell(client: TestClient) -> None:
    """Markers only base.html produces, not a coincidentally matching 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert '<meta name="color-scheme" content="light dark" />' in body
    # Each href carries a `?v=<mtime>` cache-busting suffix now, so
    # these check the prefix rather than an exact match on the old URL.
    assert '<link rel="stylesheet" href="/static/vendor/pico/pico.min.css?v=' in body
    assert '<link rel="stylesheet" href="/static/css/voxtrama.min.css?v=' in body


def test_root_response_has_no_external_resource_url(client: TestClient) -> None:
    """No external resource in what the client receives, not just the source
    on disk that test_web_shell.py already scans.
    """
    response = client.get("/")
    offenders = _EXTERNAL_URL.findall(response.text)
    assert not offenders, f"external resource URLs in served HTML: {offenders}"


def test_static_voxtrama_css_is_served() -> None:
    client = TestClient(create_app())
    response = client.get("/static/css/voxtrama.min.css")
    assert response.status_code == 200
    assert "GENERATED FILE" in response.text


def test_static_pico_css_is_served() -> None:
    client = TestClient(create_app())
    response = client.get("/static/vendor/pico/pico.min.css")
    assert response.status_code == 200


def test_root_declares_the_negotiated_locale(client: TestClient) -> None:
    """No `?lang`, no Accept-Language: negotiation falls back to English,
    and base.html's `<html lang>` must say so too, not something fixed.
    """
    response = client.get("/")
    assert 'lang="en"' in response.text


def test_lang_query_param_reaches_base_html_as_the_declared_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """`/?lang=it` must render an Italian page that also declares itself
    Italian. The defect this fixes let it render Italian while `lang="en"`.
    """
    monkeypatch.setattr(catalogs, "PACKAGE_LOCALES_DIR", tmp_path / "locales")
    write_catalog(tmp_path / "locales", "it", _EMPTY_ITALIAN_PO)

    response = client.get("/?lang=it")

    assert 'lang="it"' in response.text


def test_lang_query_param_reaches_the_route_as_a_negotiated_locale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """Proves the negotiation mechanism: the locale TranslatorDep resolves
    for `?lang=it` is the one shell() passes on to the render,
    regardless of what the page itself shows with it.

    Spies on page_context rather than render_context: every
    page now goes through the one helper that carries both the translator
    and the theme, so that is where the negotiated locale passes.
    """
    monkeypatch.setattr(catalogs, "PACKAGE_LOCALES_DIR", tmp_path / "locales")
    write_catalog(tmp_path / "locales", "it", _EMPTY_ITALIAN_PO)
    seen_locales: list[str] = []
    original_page_context = shell_route.page_context

    def _spy(session, translator, **extra):
        seen_locales.append(translator.locale)
        return original_page_context(session, translator, **extra)

    monkeypatch.setattr(shell_route, "page_context", _spy)

    response = client.get("/?lang=it")

    assert response.status_code == 200
    assert seen_locales == ["it"]
