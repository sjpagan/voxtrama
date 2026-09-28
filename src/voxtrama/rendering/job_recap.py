"""The Recap tab of a concluded job.

The recap is what the job's generative steps produced, read as a
document instead of cards. There is one section per kind: the summary's
key points first, then decisions, concepts, themes (rendering.run_output's
kinds, never a taxonomy the data does not carry). Every point has its
source (speaker · time) and every section its provenance (workflow ·
skill · model). Built from the cards rendering.run_output
already made, so the Transcript and Recap tabs can never disagree about
a claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.humanize import human_clock
from voxtrama.rendering.run_output import OutputItemView, ProvenanceView
from voxtrama.rendering.run_transcript import TranscriptRowView

# The summary is the document someone opens a job for. The lists follow.
_ORDER = ("key_point", "decision", "concept", "theme")


@dataclass(frozen=True)
class RecapPoint:
    text: str
    speaker: str | None
    time: str | None
    start: float | None
    needs_review: bool
    edited: bool = False  # A person corrected it


@dataclass(frozen=True)
class RecapSection:
    kind: str
    points: tuple[RecapPoint, ...]
    provenance: ProvenanceView


def speaker_at(rows: tuple[TranscriptRowView, ...], seconds: float | None) -> str | None:
    """Who was speaking at `seconds`: the row that contains it, else the last one before."""
    if seconds is None:
        return None
    found = None
    for row in rows:
        if row.start > seconds + 0.05:
            break
        found = row
    return found.speaker if found is not None else None


def _point(item: OutputItemView, rows: tuple[TranscriptRowView, ...]) -> RecapPoint:
    start = item.evidence_start
    text = f"{item.heading}: {item.text}" if item.heading else item.text
    return RecapPoint(
        text=text,
        speaker=speaker_at(rows, start),
        time=human_clock(start) if start is not None else None,
        start=start,
        needs_review=item.needs_review,
        edited=item.edited,
    )


def job_recap(
    items: tuple[OutputItemView, ...], rows: tuple[TranscriptRowView, ...]
) -> tuple[RecapSection, ...]:
    """One section per (kind, provenance), in `_ORDER`. Empty for a transcript-only job."""
    groups: dict[tuple[str, ProvenanceView], list[RecapPoint]] = {}
    for item in items:
        groups.setdefault((item.kind, item.provenance), []).append(_point(item, rows))
    ordered = sorted(groups.items(), key=lambda entry: _ORDER.index(entry[0][0]))
    return tuple(
        RecapSection(kind=kind, points=tuple(points), provenance=provenance)
        for (kind, provenance), points in ordered
    )
