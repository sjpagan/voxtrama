"""Plural forms come from the catalog's own CLDR rule, not hand-written logic.

Polish is the standard example of the case a homemade JSON catalog
gets wrong: three forms (one, few, many), selected by a formula that is
not "singular vs plural". `pybabel init -l pl` would fill this rule in
from CLDR automatically. The test writes it out explicitly so the fixture
carries no dependency on running that command.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.catalog import write_catalog

from voxtrama.i18n import catalogs
from voxtrama.i18n.translator import Translator

_POLISH_PLURAL_RULE = "(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2)"

_POLISH_PO = f"""
msgid ""
msgstr ""
"Content-Type: text/plain; charset=utf-8\\n"
"Plural-Forms: nplurals=3; plural={_POLISH_PLURAL_RULE};\\n"

msgid "%(n)d recording"
msgid_plural "%(n)d recordings"
msgstr[0] "%(n)d nagranie"
msgstr[1] "%(n)d nagrania"
msgstr[2] "%(n)d nagran"
"""


@pytest.fixture
def polish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Translator:
    monkeypatch.setattr(catalogs, "PACKAGE_LOCALES_DIR", tmp_path)
    write_catalog(tmp_path, "pl", _POLISH_PO)
    translations = catalogs.load_translations("pl", data_dir=None)
    return Translator(locale="pl", translations=translations)


def _plural(polish: Translator, n: int) -> str:
    return polish.ngettext("%(n)d recording", "%(n)d recordings", n) % {"n": n}


def test_the_one_form_is_used_for_a_single_item(polish: Translator) -> None:
    assert _plural(polish, 1) == "1 nagranie"


def test_the_few_form_is_used_for_small_counts_ending_in_2_to_4(polish: Translator) -> None:
    assert _plural(polish, 2) == "2 nagrania"


def test_the_many_form_is_used_for_counts_the_other_two_forms_do_not_cover(
    polish: Translator,
) -> None:
    assert _plural(polish, 5) == "5 nagran"
