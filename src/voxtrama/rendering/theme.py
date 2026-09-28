"""Which theme a page renders in, and what the control says about it.

The order is fixed: an explicit choice, else the system's
preference, else **dark**. The three-block CSS in base/_theme.scss already
implements all of it. This module only decides which of the three
choices is stored, and so whether `<html>` carries a `data-theme`
attribute at all.

**"Auto" writes no attribute.** This is the mechanism, not an
optimisation: `prefers-color-scheme` only works when nothing overrides
it, and `data-theme="auto"` would match no rule in the stylesheet,
leaving every page on the unconditional default whatever the system
says. Writing the third state into the attribute would silently break
the feature, so `attribute()` below returns None for it and the template
omits the attribute.

Rendering the attribute server-side also removes the flash of the wrong
theme: the document never exists without the choice applied, because
the choice is in the first bytes. No JavaScript is involved in this
feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from voxtrama.db.people import NoLocalUserError, local_user


class Theme(StrEnum):
    """The three states the control offers. Stored on the user row (migration 0018)."""

    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


DEFAULT_THEME = Theme.AUTO


@dataclass(frozen=True)
class ThemeChoice:
    """One entry in the control: which theme, and whether it is the current one."""

    value: Theme
    active: bool


def stored_theme(session: Session) -> Theme:
    """The local user's choice, or the default when there is no user or no valid value.

    A value the enum does not know (a hand-edited database, a column
    restored from a future version) reads as the default instead of
    raising. A preference nobody can parse is no reason to refuse to
    serve a page.
    """
    try:
        raw = local_user(session).theme
    except NoLocalUserError:
        return DEFAULT_THEME
    try:
        return Theme(raw)
    except ValueError:
        return DEFAULT_THEME


def attribute(theme: Theme) -> str | None:
    """The value for `<html data-theme>`, or None when the attribute must be absent.

    None for AUTO (see the module docstring): the absent attribute lets
    prefers-color-scheme decide, and any string here would defeat it.
    """
    return None if theme is Theme.AUTO else theme.value


def theme_choices(current: Theme) -> list[ThemeChoice]:
    """The three entries, in a fixed order, with the current one marked.

    Order is light, dark, auto: the two explicit states first and "let
    something else decide" last, so the list reads as two answers and an
    opt-out instead of three equal options.
    """
    return [ThemeChoice(value=value, active=value is current) for value in Theme]
