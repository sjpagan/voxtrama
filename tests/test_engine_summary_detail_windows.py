"""Each window asks for its share of the points the level promises.

Level 5 too, since it has a count: one point per minute of
recording, at least 15 and at most 40.
"""

from __future__ import annotations

from voxtrama.db.models.transcript import Segment
from voxtrama.engine.summary_detail import (
    DETAIL_INSTRUCTIONS,
    detail_instruction,
    points_for,
    recording_minutes,
)


def test_one_window_keeps_the_level_s_own_sentence() -> None:
    assert detail_instruction(3, windows=1) == DETAIL_INSTRUCTIONS[3]


def test_the_points_are_shared_between_the_windows() -> None:
    assert "about 2 points" in detail_instruction(3, windows=4)
    assert "one of 4 parts" in detail_instruction(3, windows=4)


def test_a_window_is_asked_for_at_least_one_point() -> None:
    assert "about 1 point," in detail_instruction(1, windows=6)


def test_level_five_asks_one_point_per_minute_within_bounds() -> None:
    assert points_for(5, 16.0) == 16
    assert points_for(5, 3.0) == 15
    assert points_for(5, 120.0) == 40


def test_level_five_asks_more_than_level_four() -> None:
    """The defect: level 5 had no number, and a small model gave fewer points than 4."""
    assert points_for(5, 0.0) > points_for(4, 0.0)
    assert "about 16 points" in detail_instruction(5, minutes=16.0)
    assert "four to six sentences" in detail_instruction(5, minutes=16.0)


def test_level_five_is_shared_between_the_windows_too() -> None:
    sentence = detail_instruction(5, windows=4, minutes=40.0)
    assert "one of 4 parts" in sentence
    assert "about 10 points" in sentence


def test_the_recording_s_length_is_its_last_segment_s_end() -> None:
    segments = [Segment(start=0.0, end=60.0, text="a"), Segment(start=60.0, end=960.0, text="b")]
    assert recording_minutes(segments) == 16.0
    assert recording_minutes([]) == 0.0


def test_no_instruction_keeps_a_placeholder() -> None:
    for level in range(1, 6):
        assert "{" not in detail_instruction(level, minutes=16.0)
