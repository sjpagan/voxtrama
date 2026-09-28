"""A string absent from an otherwise real catalog shows in English.

Never as a raw key: that is a failure worse than seeing a
word in a language nobody in the room speaks, because a key looks like a
bug and a foreign word does not.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.catalog import write_catalog

from voxtrama.i18n import catalogs
from voxtrama.i18n.translator import Translator

_INCOMPLETE_ITALIAN_PO = """
msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"

msgid "Recordings"
msgstr "Registrazioni"
"""


@pytest.fixture
def incomplete_italian(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Translator:
    """A real, loaded Italian catalog that only covers one of two strings."""
    monkeypatch.setattr(catalogs, "PACKAGE_LOCALES_DIR", tmp_path)
    write_catalog(tmp_path, "it", _INCOMPLETE_ITALIAN_PO)
    translations = catalogs.load_translations("it", data_dir=None)
    return Translator(locale="it", translations=translations)


def test_a_translated_string_uses_the_catalog(incomplete_italian: Translator) -> None:
    assert incomplete_italian.gettext("Recordings") == "Registrazioni"


def test_a_string_missing_from_the_catalog_falls_back_to_the_english_source(
    incomplete_italian: Translator,
) -> None:
    """Never a raw key: the msgid *is* the English text, so the
    fallback reads as a sentence, not as something like "run.detail.title"."""
    assert incomplete_italian.gettext("Delete recording") == "Delete recording"
