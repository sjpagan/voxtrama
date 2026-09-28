"""Cutting a long transcript into windows: size, pauses, bridges."""

from __future__ import annotations

from voxtrama.db.models.transcript import Segment
from voxtrama.engine.transcript_windows import (
    WINDOW_CHARS,
    Window,
    split_windows,
    window_text,
)


def _segments(count: int, chars: int = 99, pause_every: int = 0) -> list[Segment]:
    segments, clock = [], 0.0
    for index in range(count):
        gap = 5.0 if pause_every and index % pause_every == 0 else 0.2
        clock += gap
        segments.append(Segment(start=clock, end=clock + 4.0, text=f"{index:03d}" + "x" * chars))
        clock += 4.0
    return segments


def test_a_transcript_that_fits_is_one_window() -> None:
    segments = _segments(20)

    assert split_windows(segments) == [Window(0, 20)]


def test_every_segment_lands_in_exactly_one_window() -> None:
    segments = _segments(600)

    windows = split_windows(segments)

    assert len(windows) > 1
    assert windows[0].start == 0 and windows[-1].end == 600
    assert all(a.end == b.start for a, b in zip(windows, windows[1:], strict=False))


def test_a_window_stays_within_the_tolerance() -> None:
    windows = split_windows(_segments(600))

    for window in windows[:-1]:
        size = (window.end - window.start) * 103
        assert WINDOW_CHARS * 0.85 <= size <= WINDOW_CHARS * 1.15


def test_the_cut_falls_in_the_longest_pause() -> None:
    segments = _segments(600, pause_every=110)

    first = split_windows(segments)[0]

    assert first.end == 110


def test_a_window_reads_its_neighbours_as_context_only() -> None:
    segments = _segments(600)
    windows = split_windows(segments)

    text = window_text(segments, windows[1], len(windows))

    earlier, part = text.split("[The part to work on]")
    assert segments[windows[1].start - 1].text in earlier
    assert len(earlier) < 1800
    assert segments[windows[1].start].text in part
    assert "[Later in the recording, context only]" in part
