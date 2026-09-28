"""Date and number formatting through Babel, keyed on the negotiated locale.

The project uses gettext instead of a homemade catalog specifically so this
comes from CLDR data rather than hand-rolled formatting: a date's word
order and a decimal separator are locale choices exactly like a
translated string, and the rules Babel ships already get the lesser-known
cases right (Italian keeps the year unpadded, Polish points months
before days) rather than us guessing case by case.
"""

from __future__ import annotations

from datetime import date, datetime

from babel.dates import format_date as _format_date
from babel.dates import format_datetime as _format_datetime
from babel.dates import format_time as _format_time

from voxtrama.i18n.translator import Translator


def format_date(translator: Translator, value: date | datetime) -> str:
    """Render `value` the way `translator.locale` expects a date to look."""
    return _format_date(value, locale=translator.locale)


def format_datetime(translator: Translator, value: datetime) -> str:
    """Render `value` with both date and time, `translator.locale`'s way.

    For a list ordered by this value (the Runs list), the date alone is
    not enough: two rows created the same day render identically and the
    order between them becomes unverifiable. The time is what tells them
    apart.
    """
    return _format_datetime(value, locale=translator.locale)


def format_time(translator: Translator, value: datetime) -> str:
    """Render `value`'s time only (no date), `translator.locale`'s way.

    The run page's title already carries the date (a run's own name,
    not its workflow's), so its meta line needs only the time.
    `format_datetime` above would repeat the date.
    """
    return _format_time(value, locale=translator.locale)
