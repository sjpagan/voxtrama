"""rendering.job_turns: one bubble per speaker turn."""

from __future__ import annotations

from voxtrama.rendering.job_turns import job_turns
from voxtrama.rendering.run_transcript import TranscriptRowView


def _row(start: float, end: float, speaker: str | None, color: int = 1) -> TranscriptRowView:
    return TranscriptRowView(
        id=f"s{start}",
        start=start,
        end=end,
        time="",
        speaker=speaker,
        speaker_color=color,
        text=f"at {start}",
    )


def test_a_speaker_change_always_starts_a_turn() -> None:
    turns = job_turns((_row(0, 2, "A"), _row(2, 4, "B", 2)), pause=10)

    assert [turn.speaker for turn in turns] == ["A", "B"]
    assert [turn.side for turn in turns] == ["left", "right"]


def test_a_pause_at_or_over_the_threshold_splits_one_speakers_turn() -> None:
    rows = (_row(0, 2, "A"), _row(2.5, 4, "A"), _row(5.5, 7, "A"))

    turns = job_turns(rows, pause=1.5)

    assert [len(turn.segments) for turn in turns] == [2, 1]
    assert turns[0].text == "at 0 at 2.5"
    assert (turns[0].start, turns[0].end) == (0, 4)


def test_no_rows_no_turns() -> None:
    assert job_turns((), pause=1.5) == ()
