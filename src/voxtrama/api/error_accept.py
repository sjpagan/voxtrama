"""Whether a request prefers an HTML page over the RFC 9457 JSON body every
request failure otherwise gets.

Only a request whose Accept explicitly lists text/html, at least as
preferred as application/json, counts as wanting a page: a browser's own
default Accept header does exactly that. `Accept: */*` (curl with no
flags, most non-browser clients) names nothing explicitly and stays JSON,
the same as sending no Accept header at all.
"""

from __future__ import annotations

from fastapi import Request

_HTML = "text/html"
_JSON = "application/json"


def _qualities(header: str) -> dict[str, float]:
    """media-type -> q, first occurrence wins, default q is 1.0.

    Parameters after q are not read: nothing this module compares needs
    them, the same simplification i18n.negotiation's own Accept-Language
    parser makes for language tags.
    """
    qualities: dict[str, float] = {}
    for part in header.split(","):
        media_type, _, quality_part = part.strip().partition(";q=")
        media_type = media_type.strip().lower()
        if not media_type or media_type in qualities:
            continue
        try:
            qualities[media_type] = float(quality_part) if quality_part else 1.0
        except ValueError:
            qualities[media_type] = 1.0
    return qualities


def wants_html(request: Request) -> bool:
    """True when `request` should get a page instead of a problem+json body."""
    accept = request.headers.get("accept")
    if not accept:
        return False
    qualities = _qualities(accept)
    if _HTML not in qualities:
        return False
    return qualities[_HTML] >= qualities.get(_JSON, 0.0)
