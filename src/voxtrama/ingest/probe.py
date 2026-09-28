"""Reads what ffprobe knows about a file, before anything is copied.

Split out of local_file.py, which grew past the project's line limit once
probing had to report sample_rate and channels alongside duration and
media_format. This module has no logic of its own worth reading next to
that one ffprobe call and the JSON it returns.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from voxtrama.ingest.errors import UnsupportedMediaError

# The containers an upload may be, restricted for security. ffmpeg also
# reads playlists (hls, concat), whose lines point at other files: an
# uploaded `.m3u8` naming a path made ffmpeg transcribe another recording
# on disk.
AUDIO_FORMATS = frozenset(
    {"wav", "w64", "rf64", "mp3", "flac", "ogg", "mov", "mp4", "m4a", "matroska", "webm",
     "aac", "aiff", "caf", "asf", "amr", "avi", "mpeg", "mpegts", "wv"}
)  # fmt: skip


def _run_ffprobe(source: Path) -> dict:
    """Run ffprobe on `source` and return its parsed JSON report."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(source),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise UnsupportedMediaError("ffprobe is not installed") from exc

    if result.returncode != 0:
        raise UnsupportedMediaError(
            f"ffprobe could not read {source.name}: {result.stderr.strip()}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise UnsupportedMediaError(f"ffprobe returned no usable output for {source.name}") from exc


def probe_media(source: Path) -> tuple[float, str, int, int]:
    """Return (duration_seconds, media_format, sample_rate, channels) for `source`.

    All four come from ffprobe, run before anything is copied: a file
    ffprobe cannot make sense of is rejected without spending the I/O to
    copy it first. sample_rate and channels are the first audio stream's
    own, the same two ingest.resample.needs_resample decides on.
    """
    probe = _run_ffprobe(source)
    formats = set(probe.get("format", {}).get("format_name", "").split(","))
    if not formats & AUDIO_FORMATS:
        raise UnsupportedMediaError(f"{source.name} is not an audio or video file")

    streams = probe.get("streams", [])
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if audio_stream is None:
        raise UnsupportedMediaError(f"{source.name} has no audio stream")

    format_info = probe.get("format", {})
    duration_raw = format_info.get("duration")
    if duration_raw is None:
        raise UnsupportedMediaError(f"ffprobe could not determine the duration of {source.name}")

    media_format = format_info.get("format_name", "").split(",")[0]
    return (
        float(duration_raw),
        media_format,
        int(audio_stream.get("sample_rate", 0)),
        int(audio_stream.get("channels", 0)),
    )
