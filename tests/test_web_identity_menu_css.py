"""The identity menu's alignment, pinned in the generated CSS.

Same CSS-reading approach as test_web_shell_theme.py, and the same reason
for it: `make css` proves the SCSS compiles, not that the row it produces
still lines up. The defect these tests pin is the one a markup test alone
cannot see: components/header.html's own tests (test_web_identity_menu.py)
render the menu closed, the state in which Pico's own [open]
margin-bottom never applies, so a regression there passed silently until
someone opened the menu by hand. Pico gives a <details> a margin-bottom of
its own (documented next to .vx-identity in _shell.scss) *and*, separately,
gives its <summary> one the moment the <details> opens: two distinct
defaults on the same element, so a fix for the first does not cover the
second, and a test for the first does not catch the second going missing
either.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = REPO_ROOT / "src" / "voxtrama" / "web" / "static" / "css" / "voxtrama.min.css"


def _css() -> str:
    return re.sub(r"/\*.*?\*/", "", CSS_PATH.read_text(encoding="utf-8"), flags=re.S)


def test_the_identity_details_has_no_margin_of_its_own() -> None:
    """Pico's own bottom margin on every <details>, closed: left alone it
    grows .vx-header__actions past the badge's 45px and pushes the badge
    down to re-center in the taller row.
    """
    assert ".vx-identity{position:relative;margin:0}" in _css()


def test_the_identity_summary_gets_no_margin_when_open_either() -> None:
    """The same row, but with the <details> open: Pico's [open] state adds
    its own margin-bottom to the <summary>, a second default distinct from
    the one above, and the badge sinks the same 10px if this rule goes
    missing.
    """
    assert ".vx-identity[open]>summary{margin-bottom:0}" in _css()
