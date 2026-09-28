"""How long a run is expected to take, as opposed to how long it may take.

engine.timeout answers a different question: the budget past which the
queue kills a job, deliberately generous because killing a run mid-way
throws away work. Showing that number to a person would be a lie in the
other direction ("about 86 minutes" for a run that takes 56).

A person is owed the honest one, before the run starts:
an announced wait is a wait, an unannounced wait is a fault. So this
reuses the same measured costs without the safety factor.
"""

from __future__ import annotations

from voxtrama.engine.timeout import (
    ASR_MODEL_SIZE_MULTIPLIER,
    ASR_SECONDS_PER_AUDIO_SECOND,
    DIARIZATION_SECONDS_PER_AUDIO_SECOND,
    MINIMUM_DOWNLOAD_BANDWIDTH_BYTES_PER_SECOND,
)
from voxtrama.transcription.profiles import HardwareProfile, resolve_profile


def estimate_processing_seconds(duration_seconds: float, profile: HardwareProfile) -> float:
    """Expected CPU time for `duration_seconds` of audio on `profile`.

    The measured cost, with no margin added: this is what someone is told
    to expect, and padding it to be safe would teach them the estimate is
    worthless.
    """
    multiplier = ASR_MODEL_SIZE_MULTIPLIER[resolve_profile(profile).model_size]
    per_second = ASR_SECONDS_PER_AUDIO_SECOND * multiplier + DIARIZATION_SECONDS_PER_AUDIO_SECOND
    return duration_seconds * per_second


def estimate_download_seconds(missing_bytes: int) -> float:
    """Expected download time for `missing_bytes`, at the floor bandwidth.

    The same floor the timeout budget uses (1 MB/s): slow enough that most
    connections beat it, so the figure quoted is a ceiling a user is
    pleased to miss rather than an optimism they resent.
    """
    return missing_bytes / MINIMUM_DOWNLOAD_BANDWIDTH_BYTES_PER_SECOND
