"""TranslatorDep: per-request, never shared across requests.

A module-level Translations object or gettext.install() would make the
locale a property of the process, not of the request: invisible until
two requests in different languages hit the same running process. This
builds a tiny app around the real dependency and does exactly that.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.catalog import write_catalog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from voxtrama.config.settings import Settings, get_settings
from voxtrama.i18n import catalogs
from voxtrama.i18n.dependency import TranslatorDep

_ITALIAN_PO = """
msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"

msgid "Hello"
msgstr "Ciao"
"""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(catalogs, "PACKAGE_LOCALES_DIR", tmp_path / "package")
    write_catalog(tmp_path / "package", "it", _ITALIAN_PO)

    app = FastAPI()

    @app.get("/greeting")
    def greeting(translator: TranslatorDep) -> dict[str, str]:
        return {"locale": translator.locale, "text": translator.gettext("Hello")}

    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    return TestClient(app)


def test_accept_language_it_receives_the_catalog_string(client: TestClient) -> None:
    response = client.get("/greeting", headers={"Accept-Language": "it"})
    assert response.json() == {"locale": "it", "text": "Ciao"}


def test_accept_language_en_receives_english(client: TestClient) -> None:
    response = client.get("/greeting", headers={"Accept-Language": "en"})
    assert response.json() == {"locale": "en", "text": "Hello"}


def test_the_lang_query_parameter_is_the_explicit_choice_and_wins(client: TestClient) -> None:
    response = client.get("/greeting?lang=it", headers={"Accept-Language": "en"})
    assert response.json() == {"locale": "it", "text": "Ciao"}


def test_two_requests_in_different_languages_do_not_contaminate_each_other(
    client: TestClient,
) -> None:
    """Same TestClient, same underlying app instance, interleaved languages."""
    first = client.get("/greeting", headers={"Accept-Language": "it"})
    second = client.get("/greeting", headers={"Accept-Language": "en"})
    third = client.get("/greeting", headers={"Accept-Language": "it"})

    assert first.json()["text"] == "Ciao"
    assert second.json()["text"] == "Hello"
    assert third.json()["text"] == "Ciao"
