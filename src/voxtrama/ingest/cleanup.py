"""A cleaned copy of a recording, the one Whisper transcribes.

Measured on the same 16-minute recording: filtered and levelled before
Whisper, the audio gave a transcript with punctuation and "Visual Studio
Code"; handed to Whisper as uploaded, it gave neither. The filter chain:

- `highpass=f=80`: drops hum and handling noise below the voice;
- `afftdn=nf=-25`: spectral noise reduction, fans and room tone;
- `loudnorm=I=-16:TP=-1.5:LRA=11`: one even volume, so a quiet speaker
  is not read as silence by the VAD.

The copy is a sibling of the recording, like ingest.resample's, made once
and reused. Only transcription reads it: the original stays what the
caller gave Voxtrama (content_sha256), and diarization keeps reading the
resampled copy, whose voices the noise reduction has not reshaped.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from voxtrama.ingest.errors import UnsupportedMediaError
from voxtrama.ingest.resample import TARGET_SAMPLE_RATE

logger = logging.getLogger(__name__)

AUDIO_FILTER = "highpass=f=80,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"

# Renamed with each change of AUDIO_FILTER, so no copy made with the old
# chain is ever reused.
CLEANED_FILENAME = "cleaned_16k_v1.wav"


def cleaned_sibling(stored_path: Path) -> Path:
    """Where the cleaned copy of `stored_path` lives, once made."""
    return stored_path.with_name(CLEANED_FILENAME)


def clean_for_transcription(source: Path, destination: Path) -> None:
    """Write `source` filtered, levelled, 16 kHz mono, to `destination`, via ffmpeg.

    Written under a temporary name and renamed at the end: a worker that
    dies halfway leaves no half file that the next run would take for
    finished.
    """
    partial = destination.with_name(destination.name + ".part")
    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(source),
        "-af",
        AUDIO_FILTER,
        "-ac",
        "1",
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-f",
        "wav",
        str(partial),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise UnsupportedMediaError("ffmpeg is not installed") from exc
    if result.returncode != 0:
        partial.unlink(missing_ok=True)
        raise UnsupportedMediaError(
            f"ffmpeg could not clean {source.name}: {result.stderr.strip()}"
        )
    partial.replace(destination)


def cleaned_audio(stored_path: Path) -> Path:
    """The cleaned copy of `stored_path`, made on the first call.

    A file ffmpeg cannot clean is transcribed as it is, with a warning in
    the log: the cleaning improves a transcript, it is never the reason a
    job has none.
    """
    destination = cleaned_sibling(stored_path)
    if destination.exists():
        return destination
    try:
        clean_for_transcription(stored_path, destination)
    except UnsupportedMediaError as exc:
        logger.warning("transcribing %s without cleaning: %s", stored_path.name, exc)
        return stored_path
    return destination
