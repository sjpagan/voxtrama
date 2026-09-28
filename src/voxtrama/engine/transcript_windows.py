"""A long transcript cut into windows, each small enough to reason over.

The engine decides, not the skill. Every generative step,
custom workflows included, works on windows once the transcript is longer
than one. WINDOW_CHARS is the size of a window, not a ceiling on the
transcript: an hour or three become as many windows as they need.

The numbers are measured: a window of about 12000 characters, the cut moved
up to 15% either way to fall in the longest pause, and every window read
with the tail of the one before (about 1500 characters) and the head of the
one after (about 1200), so a point made across a cut keeps its conclusion.
We cut between segments, which carry their own timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.db.models.transcript import Segment

WINDOW_CHARS = 12000
TOLERANCE = 0.15
BRIDGE_BEFORE = 1500
BRIDGE_AFTER = 1200


@dataclass(frozen=True)
class Window:
    """Segments `start` up to, not including, `end`: the part a call works on."""

    start: int
    end: int


def _size(segment: Segment) -> int:
    return len(segment.text) + 1


def _cut(segments: list[Segment], start: int, size: int) -> int:
    """Where the window from `start` ends: the longest pause in the tolerated range."""
    low, high = size * (1 - TOLERANCE), size * (1 + TOLERANCE)
    total, best, best_gap = 0, None, -1.0
    for index in range(start, len(segments)):
        total += _size(segments[index])
        if total > high and best is not None:
            break
        if total >= low and index + 1 < len(segments):
            gap = segments[index + 1].start - segments[index].end
            if gap > best_gap:
                best, best_gap = index + 1, gap
        if total >= size and best is None:
            return index + 1
    return best if best is not None else len(segments)


def split_windows(segments: list[Segment], size: int = WINDOW_CHARS) -> list[Window]:
    """The windows `segments` fall into. One window for a transcript that fits."""
    windows, start = [], 0
    while start < len(segments):
        rest = sum(_size(segment) for segment in segments[start:])
        end = len(segments) if rest <= size * (1 + TOLERANCE) else _cut(segments, start, size)
        windows.append(Window(start, end))
        start = end
    return windows or [Window(0, 0)]


def _lines(segments: list[Segment]) -> str:
    return "\n".join(segment.text for segment in segments)


def _tail(segments: list[Segment], chars: int) -> list[Segment]:
    taken: list[Segment] = []
    for segment in reversed(segments):
        if sum(_size(s) for s in taken) >= chars:
            break
        taken.insert(0, segment)
    return taken


def _head(segments: list[Segment], chars: int) -> list[Segment]:
    return list(reversed(_tail(list(reversed(segments)), chars)))


def window_text(segments: list[Segment], window: Window, count: int) -> str:
    """The transcript a call reads for `window`: its part, between its two bridges."""
    part = _lines(segments[window.start : window.end])
    if count == 1:
        return part
    before = _tail(segments[: window.start], BRIDGE_BEFORE)
    after = _head(segments[window.end :], BRIDGE_AFTER)
    blocks = []
    if before:
        blocks.append(f"[Earlier in the recording, context only]\n{_lines(before)}")
    blocks.append(f"[The part to work on]\n{part}")
    if after:
        blocks.append(f"[Later in the recording, context only]\n{_lines(after)}")
    return "\n\n".join(blocks)
