"""Jinja wiring: one shared Environment, translations per render, not per process.

`Environment.install_gettext_translations()` would set the catalog on the
Environment itself: shared, mutable, and exactly what the package
docstring in voxtrama.i18n calls the classic gettext-on-a-server bug. This
proves the alternative holds: the *same* Environment renders two
different languages back to back with no reconfiguration in between.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.catalog import write_catalog
from jinja2 import Environment, FileSystemLoader

from voxtrama.i18n import catalogs, jinja
from voxtrama.i18n.translator import Translator

_ITALIAN_PO = """
msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"

msgid "Hello"
msgstr "Ciao"
"""


@pytest.fixture
def environment(tmp_path: Path) -> Environment:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "greeting.html").write_text("{{ _('Hello') }}")
    env = Environment(loader=FileSystemLoader(template_dir))
    jinja.install(env)
    return env


def _translator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, locale: str) -> Translator:
    monkeypatch.setattr(catalogs, "PACKAGE_LOCALES_DIR", tmp_path / "package")
    write_catalog(tmp_path / "package", "it", _ITALIAN_PO)
    translations = catalogs.load_translations(locale, data_dir=None)
    return Translator(locale=locale, translations=translations)


def test_a_render_uses_the_context_translator_not_an_installed_one(
    environment: Environment, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    translator = _translator(tmp_path, monkeypatch, "it")
    template = environment.get_template("greeting.html")

    output = template.render(**jinja.render_context(translator))

    assert output == "Ciao"


def test_the_same_environment_serves_two_languages_back_to_back(
    environment: Environment, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = environment.get_template("greeting.html")
    italian = _translator(tmp_path, monkeypatch, "it")
    english = _translator(tmp_path, monkeypatch, "en")

    first = template.render(**jinja.render_context(italian))
    second = template.render(**jinja.render_context(english))
    third = template.render(**jinja.render_context(italian))

    assert [first, second, third] == ["Ciao", "Hello", "Ciao"]
