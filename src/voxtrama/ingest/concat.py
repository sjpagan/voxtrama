"""Joins consecutive audio parts into one recording.

A call recorded in pieces (the phone stopped, the recorder split the
file) is one conversation, and a job on it must be one transcript. From
day one only consecutive parts, joined one after the other in the order
the person arranged them. Parallel tracks
(separate microphones recorded together) are mixed into one recording
instead, aligned at their start, and the speakers are then told apart
by diarization as for any single file.

The parts may differ in format, rate and channels, so each is brought to
the same shape before the join: 48 kHz mono, which keeps speech intact and
is what every later step reads anyway (resample.py makes the 16 kHz copy
from it). The result is FLAC: lossless, so joining never costs quality.
ffmpeg does the work as a subprocess, same reason as resample.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from voxtrama.ingest.errors import UnsupportedMediaError
from voxtrama.ingest.probe import probe_media

JOINED_SUFFIX = ".flac"


def _filter_graph(count: int) -> str:
    shaped = "".join(
        f"[{i}:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=mono[a{i}];"
        for i in range(count)
    )
    joined = "".join(f"[a{i}]" for i in range(count))
    return f"{shaped}{joined}concat=n={count}:v=0:a=1[out]"


def _mix_graph(count: int) -> str:
    """Tracks recorded together are mixed into one,
    aligned at their start. The limiter keeps the sum from clipping."""
    shaped = "".join(
        f"[{i}:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=mono[a{i}];"
        for i in range(count)
    )
    joined = "".join(f"[a{i}]" for i in range(count))
    return f"{shaped}{joined}amix=inputs={count}:duration=longest:normalize=0,alimiter[out]"


def concatenate_parts(parts: list[Path], destination: Path, together: bool = False) -> None:
    """Write `parts` to `destination` (FLAC): in order, one after the other, or
    `together`, mixed into one as tracks recorded at the same time."""
    if len(parts) < 2:
        raise ValueError("joining needs at least two parts")
    for part in parts:  # each one an audio container, never a playlist (probe.AUDIO_FORMATS)
        probe_media(part)
    inputs = [arg for part in parts for arg in ("-i", str(part))]
    graph = _mix_graph(len(parts)) if together else _filter_graph(len(parts))
    command = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph]
    command += ["-map", "[out]", "-c:a", "flac", str(destination)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise UnsupportedMediaError("ffmpeg is not installed") from exc
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        names = ", ".join(part.name for part in parts)
        raise UnsupportedMediaError(f"ffmpeg could not join {names}: {result.stderr.strip()}")
