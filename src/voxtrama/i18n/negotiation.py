"""Choosing which locale serves a request.

The order is fixed: an explicit choice, then the request's
Accept-Language, then VOXTRAMA_DEFAULT_LOCALE, then English. Each level is
tried in turn against the locales we have a catalog for
(i18n.catalogs.available_locales). The first candidate that matches wins,
and a level that names a locale we do not have is skipped rather than
stopping the search: that is the difference between "I asked for
Klingon" and "nobody translated this yet".
"""

from __future__ import annotations

from collections.abc import Collection

DEFAULT_LOCALE = "en"


def _accept_language_tags(header: str) -> list[str]:
    """Language tags from an Accept-Language header, best quality first.

    Ties keep the header's own order, which is what RFC 9110 asks for and
    what a reader expects: the first tag listed is the browser's actual
    preference among equals.
    """
    tags: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        part = part.strip()
        if not part:
            continue
        tag, _, quality_part = part.partition(";q=")
        try:
            quality = float(quality_part) if quality_part else 1.0
        except ValueError:
            quality = 1.0
        tags.append((quality, index, tag.strip()))
    tags.sort(key=lambda item: (-item[0], item[1]))
    return [tag for _, _, tag in tags]


def negotiate_locale(
    available: Collection[str],
    explicit: str | None,
    accept_language: str | None,
    default_locale: str | None,
) -> str:
    """Pick a locale from `available`, falling back to English."""
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    if accept_language:
        candidates.extend(_accept_language_tags(accept_language))
    if default_locale:
        candidates.append(default_locale)
    for tag in candidates:
        primary = tag.replace("_", "-").split("-")[0].lower()
        if primary in available:
            return primary
    return DEFAULT_LOCALE
