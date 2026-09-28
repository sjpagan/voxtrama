"""How long a run's job may take before the queue kills it, and why.

RQ's default (180 seconds) knows nothing about the audio it is timing.
The ASR alone costs 14s of CPU per 19s of audio on the "base" profile
(measured, not modelled), so anything past about four minutes of audio
died mid-run with a message that named the queue's default instead of the
recording. The number here is computed from what is being processed, and
it errs on the side of too much: a job killed mid-way throws away the work
already done, while a worker held a few minutes longer than needed just
sits idle. That asymmetry is why every constant below is rounded up,
never to the nearest value.

The budget also covers whatever this run's weights still need to download:
a first run on a fresh machine spends real minutes on the
network before touching the audio, and the same job_timeout clock was
running the whole time. See engine.timeout_message for what a run says
once this budget runs out.

This module deliberately does not take the download out of the job. A
separate `models pull`, or fetching at worker start, would be cleaner, but
the project chose to download on the first run that needs the weights. This
corrects the timeout to tell the truth about that choice without
revisiting it.
"""

from __future__ import annotations

import math
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.engine.downloads import pending_downloads
from voxtrama.engine.timeout_generative import generative_allowance
from voxtrama.transcription.profiles import HardwareProfile, resolve_profile
from voxtrama.workflow.definition import Workflow

# Measured directly: 14 seconds of CPU per 19 seconds of audio, running
# the "medium" model (the "base" hardware profile) on CPU int8.
ASR_SECONDS_PER_AUDIO_SECOND = 14 / 19

# Also measured: about 12 minutes of diarisation per hour of audio. The
# embedding model (ECAPA-TDNN, diarization/embedding.py) does not change
# with the hardware profile (the profile table only chooses the ASR model),
# so this term is the same for every profile.
DIARIZATION_SECONDS_PER_AUDIO_SECOND = (12 * 60) / (60 * 60)

# Only "medium" (the "base" profile) is measured, hence its multiplier of
# 1.0. "small" and "large-v3" are scaled from the models' published
# parameter counts (small ~244M, medium ~769M, large-v3 ~1550M, roughly
# 0.32x and 2.0x medium's compute), then rounded up instead of to the
# nearest value. "low" also pairs its lighter model with the older CPU
# assumed for that profile, so its theoretical speed-up is not
# credited in full. "high" also runs on CPU in 0.1 (no GPU
# requirement yet), so large-v3's extra cost is real, not offset by better
# hardware.
ASR_MODEL_SIZE_MULTIPLIER: dict[str, float] = {
    "small": 0.75,
    "medium": 1.0,
    "large-v3": 2.5,
}

# Guards the whole estimate against CPU variance the two measurements above
# do not capture, and against "small"/"large-v3" being modelled rather than
# measured.
SAFETY_FACTOR = 1.5

# Covers process and model start-up (importing torch, faster-whisper and
# speechbrain, and loading weights from the local cache), which a job pays
# once regardless of how long the audio is. Downloading the weights is a
# separate term, below.
STARTUP_MARGIN_SECONDS = 120

# A floor, not a guess at anyone's real connection: 1 MB/s is slow enough
# that most lines beat it, so the allowance it buys is usually unused
# margin, not a tight fit. It makes the startup example ("low" profile plus
# diarisation, 484 MB of ASR weights plus 83 MB of speaker weights, 567 MB
# total) worth about ten minutes of grace: realistic on a slow line,
# harmless on a fast one. Same direction as every other number here: the
# error costs a worker sitting idle, not a run killed mid-download.
MINIMUM_DOWNLOAD_BANDWIDTH_BYTES_PER_SECOND = 1 * 1024 * 1024


def compute_job_timeout(
    duration_seconds: float, hardware_profile: HardwareProfile, missing_download_bytes: int = 0
) -> int:
    """The job_timeout, in seconds, to grant a run over `duration_seconds` of audio.

    `missing_download_bytes` is whatever weights this run still has to
    fetch before it can start (engine.downloads.pending_downloads): 0 when everything
    is already cached, which is the same number this always granted before
    the download budget existed.
    """
    model_size = resolve_profile(hardware_profile).model_size
    multiplier = ASR_MODEL_SIZE_MULTIPLIER[model_size]
    per_audio_second = (
        ASR_SECONDS_PER_AUDIO_SECOND * multiplier + DIARIZATION_SECONDS_PER_AUDIO_SECOND
    )
    processing = duration_seconds * per_audio_second * SAFETY_FACTOR
    download_allowance = missing_download_bytes / MINIMUM_DOWNLOAD_BANDWIDTH_BYTES_PER_SECOND
    return math.ceil(STARTUP_MARGIN_SECONDS + download_allowance + processing)


def job_timeout_for(
    session: Session, recording_id: str | None, workflow: Workflow | None = None
) -> int | None:
    """The job_timeout to grant a run's queue job, or None without a Recording yet.

    A run may be created before its Recording exists (URL ingest);
    the queue backend falls back to its own default instead of being
    handed nothing. `workflow` is optional for the same reason `recording`
    has to tolerate absence: a caller without one yet gets no download
    allowance, as before this budget existed.
    """
    if recording_id is None:
        return None
    recording = session.get(Recording, recording_id)
    if recording is None:
        return None
    settings = get_settings()
    missing_bytes = _missing_download_bytes(
        workflow, settings.hardware_profile, settings.models_dir
    )
    extractive = compute_job_timeout(
        recording.duration_seconds, settings.hardware_profile, missing_bytes
    )
    return extractive + generative_allowance(workflow, recording.duration_seconds, settings)


def _missing_download_bytes(workflow: Workflow | None, profile: str, models_dir: Path) -> int:
    if workflow is None:
        return 0
    return sum(item.nominal_bytes for item in pending_downloads(workflow, profile, models_dir))
