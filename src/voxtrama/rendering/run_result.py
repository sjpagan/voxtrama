"""The view of a concluded job.

Everything GET /runs/{id}/view shows once a job has succeeded, below its
title: the settings line, the player, and the three tabs: Transcript
(bubbles per turn beside the verified cards), Explore (every segment,
searchable) and Recap (the generated document). Built from what
api.routes.run_page_result already read. Nothing here queries.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from voxtrama.db.models.transcript import Segment
from voxtrama.manifest.output import RunOutput
from voxtrama.manifest.schema import Manifest
from voxtrama.rendering.job_recap import RecapSection, job_recap, speaker_at
from voxtrama.rendering.job_regenerate import RegenerateForm
from voxtrama.rendering.job_settings_line import SettingsLine, settings_line
from voxtrama.rendering.job_turns import TurnView, job_turns
from voxtrama.rendering.run_output import OutputItemView, output_items
from voxtrama.rendering.run_transcript import TranscriptRowView, transcript_rows
from voxtrama.rendering.speakers_tab import SpeakerTabRow, speaker_tab_rows

TABS = ("transcript", "explore", "speakers", "recap", "files")


@dataclass(frozen=True)
class ResultView:
    """`tab` is the one open on arrival: Recap for a job that has one
    Transcript for a transcript-only job, or whichever
    the address asked for. `audio_src`, `recording_id`, `speakers` and
    `regenerate` are empty when the job's Recording is gone."""

    audio_src: str | None
    settings: SettingsLine
    transcript: tuple[TranscriptRowView, ...]
    turns: tuple[TurnView, ...]
    pause: float
    items: tuple[OutputItemView, ...]
    recap: tuple[RecapSection, ...]
    tab: str
    recording_id: str | None
    speakers: tuple[SpeakerTabRow, ...]
    speaker_names: tuple[str, ...]
    regenerate: RegenerateForm | None
    # (person id, name) a sentence can be moved to (db.segment_speaker).
    people: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ResultSource:
    """What the route read for one job, handed over in one piece."""

    segments: list[Segment]
    manifest: Manifest | None
    output: RunOutput | None
    workflow_title: str
    default_detail: int
    named: dict[str, tuple[str, str]] | None = None  # Label -> (person, name)


def _items(source: ResultSource, rows: tuple[TranscriptRowView, ...]) -> tuple[OutputItemView, ...]:
    if source.manifest is None or source.output is None:
        return ()
    return tuple(
        replace(item, evidence_speaker=speaker_at(rows, item.evidence_start))
        for item in output_items(source.manifest, source.output)
    )


def result_view(
    source: ResultSource,
    audio_src: str | None,
    recording_id: str | None,
    pause: float,
    tab: str | None = None,
    regenerate: RegenerateForm | None = None,
    people: tuple[tuple[str, str], ...] = (),
) -> ResultView:
    """The concluded job's view. A missing manifest or output.json leaves
    the transcript with no cards and no recap instead of failing the page."""
    rows = tuple(transcript_rows(source.segments))
    items = _items(source, rows)
    recap = job_recap(items, rows)
    default_tab = "recap" if recap else "transcript"
    return ResultView(
        audio_src=audio_src,
        settings=settings_line(source.manifest, source.workflow_title, source.default_detail),
        transcript=rows,
        turns=job_turns(rows, pause),
        pause=pause,
        items=items,
        recap=recap,
        tab=tab if tab in TABS else default_tab,
        recording_id=recording_id,
        speakers=speaker_tab_rows(source.segments, rows, source.named or {})
        if recording_id
        else (),
        speaker_names=tuple(dict.fromkeys(row.speaker for row in rows if row.speaker)),
        regenerate=regenerate,
        people=people,
    )
