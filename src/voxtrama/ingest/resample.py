"""Resamples an ingested file to 16 kHz mono when the run pipeline needs it.

diarization.embedding.read_mono_16k refuses anything but exactly 16 kHz
mono by design: silently accepting another rate would degrade attribution
without the result saying so (that function's own docstring). What was
missing was upstream of it: ingest.local_file used to copy a file as-is,
so a real recording at 44.1 or 48 kHz only met that refusal after
transcription had already spent the CPU on it.

This module never touches the file `content_sha256` was computed from: it
writes a second file, next to the original, that only the run pipeline
reads (engine.context.audio_path_for). The original stays exactly what the
caller gave Voxtrama (the privacy promise, and the one thing the
manifest's `input.sha256` can still be verified against), whether or
not a processing copy exists alongside it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from voxtrama.ingest.errors import UnsupportedMediaError

TARGET_SAMPLE_RATE = 16_000

# The sibling filename the run pipeline looks for next to every stored
# recording (engine.context.audio_path_for). Fixed rather than derived
# from the original name, so a lookup never has to guess an extension.
RESAMPLED_FILENAME = "resampled_16k.wav"


def needs_resample(media_format: str, sample_rate: int, channels: int) -> bool:
    """Whether the file this was probed from must be converted before a run.

    A WAV already at 16 kHz mono is the one shape read_mono_16k accepts
    as-is (every test fixture already is one), so leaving it
    untouched costs no I/O and changes nothing a run would see.
    """
    return not (media_format == "wav" and sample_rate == TARGET_SAMPLE_RATE and channels == 1)


def resampled_sibling(stored_path: Path) -> Path:
    """Where the 16 kHz mono copy of `stored_path` lives, if one was made."""
    return stored_path.with_name(RESAMPLED_FILENAME)


def resample_to_16k_mono(source: Path, destination: Path) -> None:
    """Write a 16 kHz mono WAV copy of `source` to `destination`, via ffmpeg.

    Runs as a subprocess rather than through a Python audio library, the
    same reason probe._run_ffprobe does: ffmpeg is already the project's
    dependency for this, and it streams the decode/encode itself. A
    21-minute recording is never held whole in this process' memory.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(source),
                "-ac",
                "1",
                "-ar",
                str(TARGET_SAMPLE_RATE),
                str(destination),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise UnsupportedMediaError("ffmpeg is not installed") from exc

    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        raise UnsupportedMediaError(
            f"ffmpeg could not resample {source.name} to 16 kHz mono: {result.stderr.strip()}"
        )
