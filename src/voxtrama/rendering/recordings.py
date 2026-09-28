"""One Recording, as pages/choose_workflow.html's header shows it.

The home page's Recordings card was folded into rendering.
recent_activity, so api.routes.workflow_choose is now this module's only
caller. See its docstring on why the split still holds: no query, no
domain decision, only turning rows the route already read into what a
template shows.

`duration` and `speaker_count` answer "what am I about to
process". Both stay None until a Transcript exists for this Recording,
never duration alone. Recording.duration_seconds is known from the moment
a file is imported, but showing it labelled "Transcribed"
(pages/choose_workflow.html's header) before any transcription ran would
claim something that has not happened yet. `speaker_counts` (a
recording_id -> (duration, speaker_estimate) pair, speaker_estimate
None until diarize sets it) carries whatever the route already found,
keyed so a caller with nothing to report for a recording passes no entry
instead of a special case.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.db.models.recording import Recording
from voxtrama.humanize import human_clock
from voxtrama.i18n.formatting import format_datetime
from voxtrama.i18n.translator import Translator


@dataclass(frozen=True)
class RecordingRow:
    """One Recording as pages/choose_workflow.html's header shows it.

    `duration`/`speaker_count` are both None for a Recording with no
    Transcript yet. The module docstring says why duration alone would
    already say too much.
    """

    id: str
    filename: str
    imported_at: str
    duration: str | None
    speaker_count: int | None


def recording_rows(
    recordings: list[Recording], translator: Translator, transcribed: dict[str, int | None]
) -> list[RecordingRow]:
    """Turn already-read Recording rows into what the header renders.

    `transcribed` maps a recording_id to its Transcript.speaker_estimate
    (None if diarize has not set it yet). A recording_id missing from it
    has no Transcript at all.
    """
    rows = []
    for recording in recordings:
        has_transcript = recording.id in transcribed
        rows.append(
            RecordingRow(
                id=recording.id,
                filename=recording.original_filename,
                imported_at=format_datetime(translator, recording.imported_at),
                duration=human_clock(recording.duration_seconds) if has_transcript else None,
                speaker_count=transcribed.get(recording.id),
            )
        )
    return rows
