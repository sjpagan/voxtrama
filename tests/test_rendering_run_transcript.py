"""Tests for rendering.run_transcript.transcript_rows.

Segment rows built directly, unsaved: this presenter only reads attributes
already on rows a route has fetched, the same convention test_rendering_
run_page.py already follows for RunStep.
"""

from __future__ import annotations

from voxtrama.db.models.person import Person
from voxtrama.db.models.transcript import Segment
from voxtrama.rendering.run_transcript import transcript_rows


def _segment(start: float, end: float, text: str, **fields: object) -> Segment:
    return Segment(id=f"seg-{start}", start=start, end=end, text=text, confidence=1.0, **fields)


def test_a_row_carries_raw_seconds_alongside_the_formatted_time() -> None:
    rows = transcript_rows([_segment(72.0, 74.5, "hello")])

    assert rows[0].start == 72.0
    assert rows[0].end == 74.5
    assert rows[0].time == "1:12"


def test_the_speaker_is_the_linked_persons_given_name_when_there_is_one() -> None:
    person = Person(id="p-1", given_name="Alex", family_name="")
    rows = transcript_rows([_segment(0.0, 1.0, "hi", speaker_label="spk0", person=person)])

    assert rows[0].speaker == "Alex"


def test_the_speaker_falls_back_to_the_raw_diarisation_label() -> None:
    """Never invent a name for a segment with none."""
    rows = transcript_rows([_segment(0.0, 1.0, "hi", speaker_label="spk0")])

    assert rows[0].speaker == "spk0"


def test_a_segment_with_neither_has_no_speaker() -> None:
    rows = transcript_rows([_segment(0.0, 1.0, "hi")])

    assert rows[0].speaker is None


def test_speaker_colours_cycle_through_four_and_repeat_on_a_fifth() -> None:
    segments = [_segment(float(i), float(i) + 1, "x", speaker_label=f"spk{i}") for i in range(5)]

    rows = transcript_rows(segments)

    assert [row.speaker_color for row in rows] == [1, 2, 3, 4, 1]


def test_the_same_speaker_keeps_the_same_colour_across_rows() -> None:
    segments = [
        _segment(0.0, 1.0, "a", speaker_label="spk0"),
        _segment(1.0, 2.0, "b", speaker_label="spk1"),
        _segment(2.0, 3.0, "c", speaker_label="spk0"),
    ]

    rows = transcript_rows(segments)

    assert rows[0].speaker_color == rows[2].speaker_color
