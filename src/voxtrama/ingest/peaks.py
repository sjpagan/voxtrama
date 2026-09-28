"""The waveform's own numbers, computed once on this machine.

The first version of the player drew its waveform in the browser:
`fetch` the whole audio file, `AudioContext.decodeAudioData`, then walk
the samples. Measured on a real 21-minute recording that means
**downloading 182 MB and holding 232 MB of decoded PCM** to draw a few
hundred bars, so `run_waveform.js` had a duration ceiling, past which it
silently drew nothing. A 21:08 recording fell 68 seconds over it, and the
player looked broken.

Here the same numbers cost the browser a few kilobytes of JSON, and the
ceiling disappears: an hour of audio costs it exactly what a minute does.

ffmpeg does the heavy part, as it already does for probing and
resampling. It is asked for **8 kHz mono**, not the file's own rate: a
level per bucket drawn at a few hundred pixels cannot show more, and the
decimation is ffmpeg's own resampler rather than ours.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from voxtrama.ingest.errors import UnsupportedMediaError
from voxtrama.ingest.peak_scale import levels_from_energy

# Enough buckets for any width: the canvas averages them into its bars. A
# third of a second on a 20-minute call keeps speech's rise and fall, in ~24 KB.
BUCKET_COUNT = 4000

# Levels are a drawing, not a measurement: 8 kHz keeps the shape and cuts
# the bytes ffmpeg has to hand over by six times against 48 kHz.
PEAK_SAMPLE_RATE = 8_000

_READ_CHUNK_BYTES = 1 << 20
_INT16_FULL_SCALE = 32768.0

# Renamed with each change of scale, so no stale cache is served.
PEAKS_FILENAME = "peaks-v3.json"


def peaks_path_for(audio_path: Path) -> Path:
    """Where the computed peaks of `audio_path` are cached.

    A sibling of the audio, inside the recording's own directory, the same
    place ingest.resample puts `resampled_16k.wav`. So deleting a run's
    recording takes its derived files with it, and nothing is written
    outside the data directory.
    """
    return audio_path.parent / PEAKS_FILENAME


def _ffmpeg_pcm_stream(audio_path: Path) -> subprocess.Popen[bytes]:
    """Start ffmpeg decoding `audio_path` to mono 16-bit PCM on stdout."""
    return subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(audio_path),
            "-ac",
            "1",
            "-ar",
            str(PEAK_SAMPLE_RATE),
            "-f",
            "s16le",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _fold_chunk(
    sums: np.ndarray, counts: np.ndarray, block: np.ndarray, offset: int, per_bucket: float
) -> None:
    """Fold one decoded chunk into the per-bucket energy, in place.

    `np.add.at`, not a Python loop: twenty-one minutes at 8 kHz are ten
    million samples, never held in memory at once.
    """
    indices = ((np.arange(block.size) + offset) / per_bucket).astype(np.int64)
    np.clip(indices, 0, sums.size - 1, out=indices)
    np.add.at(sums, indices, np.square(block / _INT16_FULL_SCALE))
    np.add.at(counts, indices, 1)


def compute_peaks(audio_path: Path, duration_seconds: float) -> list[float]:
    """One level per bucket for `audio_path`, 0.0 to 1.0 (RMS in dB, peak_scale).

    `duration_seconds` comes from the caller (ffprobe already knows it,
    see ingest.probe) rather than being counted here: the stream is read
    once, and knowing the total up front is what lets a sample land in its
    bucket without ever holding the whole signal.
    """
    total_samples = max(1, int(duration_seconds * PEAK_SAMPLE_RATE))
    per_bucket = max(1.0, total_samples / BUCKET_COUNT)
    sums = np.zeros(BUCKET_COUNT, dtype=np.float64)
    counts = np.zeros(BUCKET_COUNT, dtype=np.int64)

    process = _ffmpeg_pcm_stream(audio_path)
    consumed = 0
    try:
        assert process.stdout is not None
        while chunk := process.stdout.read(_READ_CHUNK_BYTES):
            usable = chunk[: len(chunk) - len(chunk) % 2]
            block = np.frombuffer(usable, dtype="<i2").astype(np.float64)
            _fold_chunk(sums, counts, block, consumed, per_bucket)
            consumed += block.size
    finally:
        if process.stdout:
            process.stdout.close()
        stderr = process.stderr.read() if process.stderr else b""
        process.wait()

    if process.returncode != 0:
        raise UnsupportedMediaError(
            f"ffmpeg could not read {audio_path.name}: {stderr.decode(errors='replace').strip()}"
        )
    return levels_from_energy(sums, counts)


def load_or_compute(audio_path: Path, duration_seconds: float) -> list[float]:
    """The cached peaks of `audio_path`, computing and storing them once.

    Computed on demand rather than during ingest: every
    recording already on disk would otherwise never get a waveform, and a
    recording nobody opens never pays for one. The cost lands once, on the
    first person to open that run's result.
    """
    cache = peaks_path_for(audio_path)
    try:
        cached = json.loads(cache.read_text())
        if isinstance(cached, list) and len(cached) == BUCKET_COUNT:
            return [float(level) for level in cached]
    except (OSError, ValueError):
        pass

    peaks = compute_peaks(audio_path, duration_seconds)
    try:
        cache.write_text(json.dumps(peaks))
    except OSError:
        pass  # A read-only data directory must not break the drawing.
    return peaks
