"""The four-level language order, and Accept-Language parsing."""

from __future__ import annotations

from voxtrama.i18n.negotiation import negotiate_locale

AVAILABLE = {"en", "it", "fr"}


def test_explicit_choice_wins_over_everything_else() -> None:
    locale = negotiate_locale(AVAILABLE, explicit="fr", accept_language="it", default_locale="it")
    assert locale == "fr"


def test_accept_language_wins_when_there_is_no_explicit_choice() -> None:
    locale = negotiate_locale(AVAILABLE, explicit=None, accept_language="it", default_locale="fr")
    assert locale == "it"


def test_default_locale_wins_when_neither_explicit_nor_header_match() -> None:
    locale = negotiate_locale(AVAILABLE, explicit=None, accept_language="de", default_locale="fr")
    assert locale == "fr"


def test_english_is_the_last_resort() -> None:
    locale = negotiate_locale(AVAILABLE, explicit=None, accept_language=None, default_locale=None)
    assert locale == "en"


def test_a_level_naming_an_unavailable_locale_is_skipped_not_stopped_at() -> None:
    """Asking for Klingon does not block reaching the next level down."""
    locale = negotiate_locale(AVAILABLE, explicit="tlh", accept_language="de", default_locale="it")
    assert locale == "it"


def test_accept_language_picks_the_highest_quality_tag() -> None:
    locale = negotiate_locale(
        AVAILABLE,
        explicit=None,
        accept_language="de;q=0.9, it;q=0.95, fr;q=0.1",
        default_locale=None,
    )
    assert locale == "it"


def test_accept_language_breaks_quality_ties_by_header_order() -> None:
    locale = negotiate_locale(
        AVAILABLE, explicit=None, accept_language="fr, it", default_locale=None
    )
    assert locale == "fr"


def test_accept_language_matches_on_the_primary_subtag() -> None:
    """A regional tag like it-IT still matches the plain "it" catalog."""
    locale = negotiate_locale(
        AVAILABLE, explicit=None, accept_language="it-IT", default_locale=None
    )
    assert locale == "it"
