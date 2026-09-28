"""A span of a recording as its own MP3, for the job package."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from voxtrama.ingest.audio_cut import cut_mp3

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


def _seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(out.stdout)


def test_a_span_and_the_rest_are_cut_where_asked(tmp_path: Path) -> None:
    source = tmp_path / "in.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=6", str(source)], check=True
    )

    cut_mp3(source, tmp_path / "a.mp3", 1.0, 3.0)
    cut_mp3(source, tmp_path / "b.mp3", 3.0, None)

    assert _seconds(tmp_path / "a.mp3") == pytest.approx(2.0, abs=0.15)
    assert _seconds(tmp_path / "b.mp3") == pytest.approx(3.0, abs=0.15)
