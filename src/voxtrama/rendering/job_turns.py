"""The Transcript tab of a concluded job, one bubble per speaker turn.

The ASR cuts a sentence wherever it pauses for breath, so a row per
Segment reads as a list of fragments. A turn is what a person said
before someone else spoke: consecutive segments of the same speaker are
joined, unless the silence between two of them is at least `pause`
seconds (the job's «Merge pauses under», 1.5 s by default). The
segments stay inside the turn with their times, so the bubble can show
where each fragment began.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.humanize import human_clock
from voxtrama.rendering.run_transcript import TranscriptRowView


@dataclass(frozen=True)
class TurnView:
    """One bubble. `side` puts the first speaker's colour on the left and
    the second's on the right, alternating them."""

    speaker: str | None
    speaker_color: int
    side: str
    start: float
    end: float
    time: str
    text: str
    segments: tuple[TranscriptRowView, ...]


def _turn(rows: list[TranscriptRowView]) -> TurnView:
    first = rows[0]
    return TurnView(
        speaker=first.speaker,
        speaker_color=first.speaker_color,
        side="left" if first.speaker_color % 2 else "right",
        start=first.start,
        end=rows[-1].end,
        time=human_clock(first.start),
        text=" ".join(row.text.strip() for row in rows),
        segments=tuple(rows),
    )


def job_turns(rows: tuple[TranscriptRowView, ...], pause: float) -> tuple[TurnView, ...]:
    """`rows` (already in start order) folded into turns."""
    turns: list[TurnView] = []
    current: list[TranscriptRowView] = []
    for row in rows:
        if current and (row.speaker != current[-1].speaker or row.start - current[-1].end >= pause):
            turns.append(_turn(current))
            current = []
        current.append(row)
    if current:
        turns.append(_turn(current))
    return tuple(turns)
