"""Dates and numbers render through Babel's CLDR data.

Not a hand-rolled `strftime` and not a hand-rolled decimal separator: the
locale drives both, the same way it drives which catalog answers gettext.
"""

from __future__ import annotations

from datetime import date, datetime
from gettext import NullTranslations

from voxtrama.i18n.formatting import format_date, format_datetime
from voxtrama.i18n.translator import Translator


def _translator(locale: str) -> Translator:
    return Translator(locale=locale, translations=NullTranslations())


def test_a_date_renders_in_the_english_convention() -> None:
    assert format_date(_translator("en"), date(2026, 3, 4)) == "Mar 4, 2026"


def test_the_same_date_renders_differently_in_italian() -> None:
    assert format_date(_translator("it"), date(2026, 3, 4)) == "4 mar 2026"


def test_a_datetime_carries_the_time_in_the_english_convention() -> None:
    # Two runs created the same day still need a distinguishable string
    # (rendering.runs.run_rows relies on this). The time is what does it.
    value = datetime(2026, 3, 4, 15, 45, 2)
    assert format_datetime(_translator("en"), value) == "Mar 4, 2026, 3:45:02 PM"


def test_the_same_datetime_carries_the_time_in_the_italian_convention() -> None:
    value = datetime(2026, 3, 4, 15, 45, 2)
    assert format_datetime(_translator("it"), value) == "4 mar 2026, 15:45:02"
