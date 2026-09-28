"""Reads a run's own run.log incrementally, for the run page's live panel.

logs.run_file already writes this file, one JSON object per line
(logs.run_file.RunFileHandler). This is the one place that reads it back,
with the byte offset kept between calls so a client watching a run does not cost the
disk a full re-read of a file that only grows. api.routes.run_events calls
this once per poll, the same cadence it already reads progress.json at.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from voxtrama.logs.panel_words import readable


@dataclass
class RunLogTail:
    """Tracks how far into `path` the last read got.

    A dataclass with mutable state, not a pair of free functions passed an
    offset by the caller: api.routes.run_events keeps one of these per open
    connection, for the lifetime of that connection alone. Nothing here
    survives a reconnect, the same way progress.json's dedup starts over
    "from now" rather than from the beginning (see that module's
    docstring).
    """

    path: Path
    _offset: int = 0

    @property
    def offset(self) -> int:
        """How far into `path` this tail has read: run_log_stream's own
        `id:` line on every `log` event, for a reconnect's `Last-Event-ID`."""
        return self._offset

    def read_new_lines(self) -> list[str]:
        """Every complete log line appended since the last call, already formatted.

        Reads in binary and stops at the last newline in the chunk: the
        writer (logs.run_file.RunFileHandler) appends one line plus "\\n"
        per call, but nothing stops this from being read mid-write, and a
        half-written last line is worse kept for next time than shown
        broken now. The offset only advances past a newline it
        saw, so a partial tail is picked up whole on the following poll.
        """
        if not self.path.exists():
            return []
        with self.path.open("rb") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
        last_newline = chunk.rfind(b"\n")
        if last_newline == -1:
            return []
        complete, self._offset = chunk[: last_newline + 1], self._offset + last_newline + 1
        lines = []
        for raw in complete.decode("utf-8", errors="replace").splitlines():
            formatted = _format_line(raw)
            if formatted is not None:
                lines.append(formatted)
        return lines


def tail_lines_with_offset(path: Path, limit: int) -> tuple[list[str], int]:
    """The last `limit` formatted lines of `path`, and how many bytes the read consumed.

    That byte count is where a fresh page's own render leaves off:
    api.routes.run_page seeds the SSE connection's own RunLogTail with it,
    via the same `Last-Event-ID` a reconnecting EventSource sends on its
    own, so a run.log already shown at first paint is never sent a second
    time over the wire. Read in binary, like RunLogTail.read_new_lines,
    not with a text-mode iterator: the two must agree on what a byte offset
    means, since one is what the other resumes from.
    """
    if not path.exists():
        return [], 0
    with path.open("rb") as handle:
        data = handle.read()
    lines: list[str] = []
    for raw in data.decode("utf-8", errors="replace").splitlines():
        formatted = _format_line(raw)
        if formatted is None:
            continue
        lines.append(formatted)
        if len(lines) > limit:
            lines.pop(0)
    return lines, len(data)


# The one prefix a line's own "logger" (logs.formatter.JsonFormatter's
# `record.name`) must carry to reach the panel. run.log holds every logger
# the process ever touches (RunFileHandler is not scoped to
# one), such as httpx's "HTTP Request: GET https://huggingface.co/api/..."
# on every cache lookup diarize's ECAPA-TDNN model makes, three of them
# for every line a skill reports. The file on disk keeps all of
# it, for whoever is diagnosing a failure. This is the one gate between
# that file and the run page's live panel, which only wants this
# package's narrative of a run (engine.run's "run started", engine.
# progress_file's activity lines). Every voxtrama logger is
# `logging.getLogger(__name__)`, so a dotted name starting here is never
# a third party's.
_PANEL_LOGGER_PREFIX = "voxtrama"


def _format_line(raw: str) -> str | None:
    """`raw` (one JSONL event) as the terminal panel shows it: "HH:MM:SS  msg".

    None for a line that is not a JSON object with both fields: the shape
    a half-written last line takes when read mid-write. Also None for a
    line whose "logger" is not this package's (_PANEL_LOGGER_PREFIX
    above), noise the file keeps but the panel does not show.
    """
    if not raw:
        return None
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return None
    ts, msg, logger_name = event.get("ts"), event.get("msg"), event.get("logger", "")
    if not isinstance(ts, str) or not isinstance(msg, str):
        return None
    is_own_logger = logger_name == _PANEL_LOGGER_PREFIX or logger_name.startswith(
        f"{_PANEL_LOGGER_PREFIX}."
    )
    if not is_own_logger:
        return None
    return f"{_clock(ts)}  {readable(msg, event.get('step'))}"


def _clock(ts: str) -> str:
    """`ts`'s own "HH:MM:SS", out of logs.formatter's "...THH:MM:SS.mmmZ".

    A slice, not a parse: the formatter's own timestamp shape is fixed
    (logs.formatter._timestamp), and every line this reads was written by
    it. There is no second format to tolerate.
    """
    return ts[11:19] if len(ts) >= 19 else ts
