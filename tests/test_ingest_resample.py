"""Tests for ingest.resample: converting what the run pipeline cannot read as-is.

A real recording (44.1 or 48 kHz, as any phone or conferencing tool
produces) used to reach diarization.embedding.read_mono_16k unresampled
and fail there, after transcription had already spent minutes of CPU on
it. These tests reproduce that shape without tracking a binary fixture
(test_no_tracked_media_files): ffmpeg's own null source
generates a short WAV at whatever rate a test needs, fresh, in a temp
directory, every run.
"""

from __future__ import annotations

import hashlib
import subprocess
import wave
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.engine.context import audio_path_for
from voxtrama.ingest import import_local_file
from voxtrama.ingest.resample import RESAMPLED_FILENAME, needs_resample


def _write_wav(path: Path, seconds: float = 0.5, frame_rate: int = 16000) -> None:
    """A small, real mono PCM WAV file ffprobe can read: silence, at `frame_rate`."""
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(frame_rate)
        handle.writeframes(b"\x00\x00" * int(frame_rate * seconds))


def _ffmpeg_generate(
    path: Path, sample_rate: int, sample_fmt: str = "s16", seconds: float = 0.5
) -> None:
    """A short mono WAV at `sample_rate`/`sample_fmt`, via ffmpeg's `anullsrc`.

    Used where the shape under test needs a bit depth `wave` cannot write
    (PCM_24, like the real file that exposed this), or simply to keep the fixture built the
    same way ingest.resample itself will read it back.
    """
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=mono",
            "-t",
            str(seconds),
            "-c:a",
            f"pcm_{sample_fmt}le",
            str(path),
        ],
        check=True,
    )


@pytest.mark.parametrize(
    ("media_format", "sample_rate", "channels", "expected"),
    [
        ("wav", 16000, 1, False),  # already the one shape read_mono_16k accepts
        ("wav", 48000, 1, True),  # the real recording's case
        ("wav", 44100, 1, True),
        ("wav", 16000, 2, True),  # stereo, even at the right rate
        ("mp3", 16000, 1, True),  # right rate, but not a container read_mono_16k opens
    ],
)
def test_needs_resample(media_format: str, sample_rate: int, channels: int, expected: bool) -> None:
    assert needs_resample(media_format, sample_rate, channels) is expected


def test_import_local_file_leaves_an_already_16k_mono_wav_untouched(
    tmp_path: Path, db_session: Session
) -> None:
    source = tmp_path / "clip.wav"
    _write_wav(source, frame_rate=16000)
    # audio_path_for reads get_settings().data_dir itself: the two must agree.
    paths = get_paths(get_settings().data_dir)

    recording = import_local_file(db_session, source, paths)

    stored = paths.data_dir / recording.stored_path
    assert not (stored.parent / RESAMPLED_FILENAME).exists()
    assert audio_path_for(recording) == stored


def test_import_local_file_resamples_a_higher_rate_file_for_the_run_pipeline(
    tmp_path: Path, db_session: Session
) -> None:
    """The reported case: a real recording at 48 kHz, PCM_24, mono."""
    source = tmp_path / "aigen-21min.wav"
    _ffmpeg_generate(source, sample_rate=48000, sample_fmt="s24", seconds=0.5)
    original_bytes = source.read_bytes()
    paths = get_paths(get_settings().data_dir)

    recording = import_local_file(db_session, source, paths)

    # The original is untouched (content_sha256 stays verifiable against
    # it) and duration is its own, not recomputed from the conversion.
    stored = paths.data_dir / recording.stored_path
    assert stored.read_bytes() == original_bytes
    assert recording.content_sha256 == hashlib.sha256(original_bytes).hexdigest()
    assert recording.duration_seconds == pytest.approx(0.5, abs=0.05)

    processed = audio_path_for(recording)
    assert processed != stored
    assert processed.name == RESAMPLED_FILENAME

    # The actual consumer: must not raise, which is the bug reported.
    from voxtrama.diarization.embedding import read_mono_16k

    signal = read_mono_16k(processed)
    assert len(signal) > 0


def test_import_local_file_rejects_a_file_ffmpeg_cannot_decode(
    tmp_path: Path, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file ffprobe reads but ffmpeg fails to resample must not become a
    half-imported Recording: the same all-or-nothing rule
    import_local_file already applies to a failed copy.
    """
    from voxtrama.ingest import local_file
    from voxtrama.ingest.errors import UnsupportedMediaError

    def _broken_resample(source: Path, destination: Path) -> None:
        raise UnsupportedMediaError("ffmpeg could not resample it")

    monkeypatch.setattr(local_file, "resample_to_16k_mono", _broken_resample)
    source = tmp_path / "clip.wav"
    _write_wav(source, frame_rate=48000)
    paths = get_paths(tmp_path / "data")

    with pytest.raises(UnsupportedMediaError):
        import_local_file(db_session, source, paths)

    # recordings_dir itself is already created by this point (unlike a
    # probe rejection). What must not survive is the recording's own dir.
    assert not any(paths.recordings_dir.iterdir())
