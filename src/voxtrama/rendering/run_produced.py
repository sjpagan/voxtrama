"""GET /runs/{id}/view's "What this run did produce" section.

Only a Transcript exists to preview today. The "concluded run" page is
where every other output (extracted decisions, a generative step's
answer) gets the same treatment once a run succeeds. This section only
needs the failed case: the transcript the transcribe step leaves behind
when a later step fails, never thrown away for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from voxtrama.db.models.transcript import Segment
from voxtrama.humanize import human_clock

if TYPE_CHECKING:  # rendering.job_turns reaches back here through run_transcript
    from voxtrama.rendering.job_turns import TurnView

# The design shows eight lines before the fold. A named limit
# instead of "however many fit", so a long recording's preview stays a
# preview, not the whole transcript rendered twice for a section that
# only asked for a glance.
PREVIEW_SEGMENT_COUNT = 8


@dataclass(frozen=True)
class TranscriptLineView:
    """One Segment as the preview shows it: when, who, and what was said."""

    time: str
    speaker: str | None
    text: str
    id: str | None = None  # The anchor a search result links to


@dataclass(frozen=True)
class ProducedView:
    """A transcript preview, and where the whole one lives."""

    lines: tuple[TranscriptLineView, ...]
    truncated: bool
    view_transcript_href: str
    # The preview as the job view's
    # bubbles (rendering.job_turns), built by the route from the same rows.
    turns: tuple[TurnView, ...] = ()


def speaker_name(segment: Segment) -> str | None:
    """A name for `segment`'s leading column: the linked Person's given
    name once diarisation is corrected by hand, else the raw
    diarisation label. Never both, and never invented for a segment with
    neither.

    Public: rendering.run_transcript's full-transcript column needs
    the same rule this preview applies, and a second implementation could
    drift from this one.
    """
    if segment.person is not None:
        return segment.person.given_name
    return segment.speaker_label


def produced_view(segments: list[Segment], view_transcript_href: str) -> ProducedView | None:
    """The preview for `segments`, already ordered by start. None when there are none yet.

    Only slices and formats what the route already queried in that order.
    Sorting a second time is not this module's job.
    """
    if not segments:
        return None
    preview = segments[:PREVIEW_SEGMENT_COUNT]
    lines = tuple(
        TranscriptLineView(
            time=human_clock(segment.start),
            speaker=speaker_name(segment),
            text=segment.text,
            id=segment.id,
        )
        for segment in preview
    )
    return ProducedView(
        lines=lines,
        truncated=len(segments) > PREVIEW_SEGMENT_COUNT,
        view_transcript_href=view_transcript_href,
    )
