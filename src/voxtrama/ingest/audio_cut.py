"""One span of a recording written as its own small MP3.

For the job package (api.routes.job_package): the recording in parts of
about ten minutes, each playable on its own, next to its part of the
transcript. MP3, mono, 64 kbit/s: speech stays clear and an hour of it
is about 30 MB, where a WAV would be several times that. The source file
is only read; nothing is written next to it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def cut_mp3(source: Path, target: Path, start: float, end: float | None) -> None:
    """Write `source` from `start` to `end` (None: to the end) into `target`.

    Raises subprocess.CalledProcessError when ffmpeg cannot read or write.
    """
    span = ["-ss", f"{start:.3f}"] + (["-to", f"{end:.3f}"] if end is not None else [])
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            *span,
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            str(target),
        ],
        check=True,
        capture_output=True,
    )
