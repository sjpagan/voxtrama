"""Crumb, the breadcrumb's building block.

Split out of nav.py, which is about which sections the sidebar has and
which one is current. Four branches landing together pushed nav.py past
the project's file limit, so the split was required, not just tidy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Crumb:
    """One link of the breadcrumb chain: `key` picks the translated
    label components/breadcrumb.html shows, `label` replaces it when the
    text is data (a recording's filename), and `href` is None on the last
    link, the one that says where you are.
    """

    key: str
    href: str | None = None
    label: str | None = None
