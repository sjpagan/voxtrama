"""PanelLine: one run.log line as the terminal panel needs it.

Split out of logs.tail (the project's file-length limit), the same reason
logs.panel_words was.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelLine:
    """One run.log line as the terminal panel needs it, not yet a fixed string.

    `instant` is the file's own UTC timestamp, unedited (logs.formatter's
    "...THH:MM:SS.mmmZ"): the browser is the only place that knows the
    reader's own timezone, so it is the one that turns this into a clock
    reading (web.static.js.local_time.js). `clock` is that same instant's
    "HH:MM:SS" out of the container's own UTC, kept only as the no-JavaScript
    fallback the `<time>` element's own text starts as.
    """

    instant: str
    clock: str
    message: str
