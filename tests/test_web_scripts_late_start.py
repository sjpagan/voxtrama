"""A script the job page adds late still starts (the waveform left blank).

A job followed live becomes its concluded page without a reload: run_page.js
fetches it, swaps its <main> in and appends the scripts only the result
needs (run_result.html). By then DOMContentLoaded has fired, so a script
that waits for that event alone never runs. On 27 September 2026 that left
the player's waveform empty on a finished 16-minute job until the page was
reloaded, with the peaks already served and nothing in the console.

The scripts are read, not run: whichever one listens for DOMContentLoaded
must also check `document.readyState`, and start at once when the page has
already loaded.
"""

from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "src" / "voxtrama" / "web"
JS_DIR = WEB / "static" / "js"
RESULT_TEMPLATE = WEB / "templates" / "components" / "run_result.html"


def _late_scripts() -> list[Path]:
    """The scripts run_page.js may append after the page has loaded."""
    names = re.findall(r"js/(\w+\.js)", RESULT_TEMPLATE.read_text(encoding="utf-8"))
    return [JS_DIR / name for name in sorted(set(names))]


def test_the_result_template_loads_scripts() -> None:
    assert _late_scripts(), f"no script found in {RESULT_TEMPLATE}"


def test_no_late_script_waits_only_for_dom_content_loaded() -> None:
    stuck = [
        path.name
        for path in _late_scripts()
        if "DOMContentLoaded" in (source := path.read_text(encoding="utf-8"))
        and "document.readyState" not in source
    ]
    assert stuck == [], f"these never start when run_page.js adds them late: {stuck}"
