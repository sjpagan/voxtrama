"""The 1-5 depth of a recap, as an instruction the summarize prompt carries.

One skill, `summarize`, for every depth: the job chooses a level (the
new-job form, RunChoices.summary_detail) and the level becomes a sentence
in the prompt about length and depth: 1 a few points, 5 every theme
developed with its quotes, one point per minute of recording. A
prompt without a {detail} placeholder ignores it: str.format drops a
keyword nobody asked for. A transcript split into windows asks each
window for its share of the points.
"""

from __future__ import annotations

# Level 5 used to be the only level with no number ("as many points
# as the transcript supports"). qwen3:4b read that as "a few": 8 points on
# a 16-minute recording, fewer than level 4's 12. It now asks for one point
# per minute of recording, within these bounds.
LEVEL_5_POINTS = (15, 40)

_POINTS = {1: 3, 2: 5, 3: 8, 4: 12}
_EACH = {
    1: "one short sentence each",
    2: "one or two sentences each",
    3: "two or three sentences each",
    4: "each explained in a short paragraph",
    5: "each argued in a paragraph of four to six sentences and backed by its own quote",
}

DETAIL_INSTRUCTIONS = {
    1: "Keep it to the 3 most important points only, one short sentence each.",
    2: "Give about 5 points, one or two sentences each.",
    3: "Give about 8 points covering every main topic, two or three sentences each.",
    4: "Cover every topic discussed, about 12 points, each explained in a short paragraph.",
    5: "Cover every theme exhaustively, leaving none out: about {points} points, " + _EACH[5] + ".",
}


def recording_minutes(segments) -> float:
    """How long the transcribed recording runs: its last segment's end."""
    return segments[-1].end / 60 if segments else 0.0


def points_for(level: int, minutes: float) -> int:
    """How many points `level` asks of a recording `minutes` long."""
    if level < 5:
        return _POINTS[level]
    low, high = LEVEL_5_POINTS
    return min(max(round(minutes), low), high)


def detail_instruction(level: int, windows: int = 1, minutes: float = 0.0) -> str:
    """The sentence for `level`, clamped to 1-5 so a stored value can never break a prompt.

    `minutes` is the recording's length, which sets level 5's count. With
    more than one window, the sentence asks this window for its share, at
    every level.
    """
    level = min(max(level, 1), 5)
    points = points_for(level, minutes)
    if windows <= 1:
        return DETAIL_INSTRUCTIONS[level].format(points=points)
    share = max(1, round(points / windows))
    count = "1 point" if share == 1 else f"{share} points"
    return (
        f"This is one of {windows} parts of a longer recording: for this part alone, "
        f"give about {count}, {_EACH[level]}."
    )
