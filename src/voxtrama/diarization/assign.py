"""Attach a speaker label to every Segment the ASR produced.

Diarisation and transcription cut the audio differently: the ASR emits one
Segment per utterance, diarisation emits fixed windows. Nothing guarantees
the two line up, so each Segment takes the label of whichever speaker holds
the most time inside it. It is the only rule that stays defined when a window
straddles two utterances, the normal case at a turn boundary.

The label is anonymous (`spk0`, `spk1`) and is not a person: `person_id` is
kept for a human, linked by hand, and this label survives that link rather
than being replaced by it.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.diarization.embedding import TARGET_SAMPLE_RATE, embed_windows, read_mono_16k
from voxtrama.diarization.windowing import cluster_embeddings, label_windows, make_windows

logger = logging.getLogger(__name__)

# Default ceiling on how many speakers a run may report, and the same one
# the evaluation material was built against. It caps an estimate, it
# does not set it: a run with two voices reports two. Callers override it
# through configuration (config.settings.max_speakers) rather than
# this module deciding it for every run.
_DEFAULT_MAX_SPEAKERS = 4


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def dominant_label(
    segment_start: float, segment_end: float, labelled: list[tuple[float, float, str]]
) -> str | None:
    """The speaker holding the most time inside [segment_start, segment_end].

    None when no window overlaps at all, which means the diarisation has
    nothing to say about that stretch. It stays unset because an invented
    label would read exactly like a real one downstream.
    """
    totals: dict[str, float] = defaultdict(float)
    for window_start, window_end, label in labelled:
        overlap = _overlap(segment_start, segment_end, window_start, window_end)
        if overlap > 0:
            totals[label] += overlap
    if not totals:
        return None
    return max(totals.items(), key=lambda item: item[1])[0]


def assign_speakers(
    transcript: Transcript,
    audio_path: Path,
    models_dir: Path,
    max_speakers: int = _DEFAULT_MAX_SPEAKERS,
    on_download: Callable[[int, int | None], None] | None = None,
    on_progress: Callable[[float, float | None], None] | None = None,
) -> Transcript:
    """Fill in `speaker_label` on every Segment of `transcript`, in place.

    `person_id` is never touched: linking a label to a real person is a
    separate, reversible act performed by a human, and doing it
    here would mean guessing who someone is from how they sound.

    `transcript.speaker_estimate` and `transcript.speaker_cap` are always
    set, so a run's result says what diarisation heard even when
    it exceeds what it was allowed to report: a cap applied in
    silence is a degradation that is never allowed.
    """
    signal = read_mono_16k(audio_path)
    duration = len(signal) / TARGET_SAMPLE_RATE
    windows = make_windows(duration)
    embeddings = embed_windows(signal, windows, models_dir, duration, on_download, on_progress)
    result = cluster_embeddings(embeddings, max_speakers)
    labelled = label_windows(windows, result.labels)

    for segment in transcript.segments:
        segment.speaker_label = dominant_label(segment.start, segment.end, labelled)

    transcript.speaker_estimate = result.estimated_speakers
    transcript.speaker_cap = max_speakers
    if result.estimated_speakers > max_speakers:
        logger.warning(
            "diarisation estimated %d speakers, capped to %d",
            result.estimated_speakers,
            max_speakers,
        )
    return transcript


def speaker_count(segments: list[Segment]) -> int:
    """How many distinct speakers the labels describe, ignoring unlabelled ones."""
    return len({segment.speaker_label for segment in segments if segment.speaker_label})
