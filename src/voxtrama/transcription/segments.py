"""Turns faster-whisper's own raw segments into Segment rows.

Split out of transcription.asr (the project's size limit) once
transcribe() gained a second run-level knob to document. Nothing here reads
Settings or a RunChoices: this is pure conversion, not resolution.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from voxtrama.db.models.transcript import Segment


def confidence(avg_logprob: float) -> float:
    """Turn faster-whisper's average log-probability into a 0-1 proxy."""
    return math.exp(avg_logprob)


def build_segments(
    raw_segments,
    total: float | None,
    on_progress: Callable[[float, float | None], None] | None,
) -> list[Segment]:
    """Turn faster-whisper's segments into Segment rows, reporting position as they arrive.

    `total` is known before this loop starts: model.transcribe() returns
    info.duration before the segment generator is consumed, so the
    same total accompanies every call rather than each one guessing it
    afresh. Position is `segment.end`, the one point in the whole step that
    already knows both how far in it is and how long the audio runs.
    """
    segments = []
    for segment in raw_segments:
        segments.append(
            Segment(
                start=segment.start,
                end=segment.end,
                text=segment.text.strip(),
                confidence=confidence(segment.avg_logprob),
                person_id=None,
            )
        )
        if on_progress is not None:
            on_progress(segment.end, total)
    return segments
