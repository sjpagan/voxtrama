"""GET /runs/{id}/view's full transcript column, for a succeeded run.

rendering.run_produced builds an eight-line preview for a failed run.
This is the whole thing: every Segment the route already queried, in
start order. `speaker_name` is that module's rule (for now
a bare speaker_label is shown as-is, never a guessed name), imported
instead of reimplemented so the two transcripts never disagree about
what a speaker is called.

`start`/`end` are carried as raw seconds, not only the formatted `time`
column. static/js/run_result.js reads them off the DOM (a
`data-start`/`data-end` pair) to seek the player and to decide which
rows an extracted result's evidence interval covers. It is the same
tolerance-free comparison engine.anchor_index.AnchorIndex._interval_for
used to write that interval: a segment's start and end, never a sub-span
of either.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.db.models.transcript import Segment
from voxtrama.humanize import human_clock
from voxtrama.rendering.run_produced import speaker_name

# Each speaker gets a colour cycling through
# four (abstracts/_tokens.scss's speaker-1..4). A fifth speaker in the
# same recording repeats the first colour instead of growing the palette
# for a case the design never shows.
SPEAKER_COLOR_COUNT = 4


@dataclass(frozen=True)
class TranscriptRowView:
    """One Segment as the transcript column shows it: when, who, what, and
    where it sits in the audio.

    `id` is `Segment.id`, carried so a future evidence link that names a
    specific segment (not only a time range) has something to point at.
    The page's JS does not use it and matches by time instead (see the
    module docstring).
    """

    id: str
    start: float
    end: float
    time: str
    speaker: str | None
    speaker_color: int
    text: str
    person_id: str | None = None  # Who a person set this sentence to, if anyone


def transcript_rows(segments: list[Segment]) -> list[TranscriptRowView]:
    """Every row of `segments`, already ordered by start by the caller, as
    rendering.run_produced.produced_view also never sorts a second time.

    A speaker's colour is assigned the first time their name (or lack of
    one) is seen, then reused for every later row of that speaker. It is
    not derived from the name, so two recordings with the same speaker
    order look the same whatever the speakers are called.
    """
    colors: dict[str | None, int] = {}
    rows = []
    for segment in segments:
        name = speaker_name(segment)
        if name not in colors:
            colors[name] = len(colors) % SPEAKER_COLOR_COUNT + 1
        rows.append(
            TranscriptRowView(
                id=segment.id,
                start=segment.start,
                end=segment.end,
                time=human_clock(segment.start),
                speaker=name,
                speaker_color=colors[name],
                text=segment.text,
                person_id=segment.person_id,
            )
        )
    return rows
