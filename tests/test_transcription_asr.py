"""Tests for voxtrama.transcription.asr.transcribe."""

from __future__ import annotations

import math
import os
import wave
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.ingest import import_local_file
from voxtrama.transcription import transcribe
from voxtrama.transcription.segments import build_segments


@dataclass
class _FakeRawSegment:
    """Stands in for faster-whisper's own segment: only the fields build_segments reads."""

    start: float
    end: float
    text: str
    avg_logprob: float


def test_build_segments_reports_position_against_the_total_duration() -> None:
    """A fake generator: the total (info.duration) is known before
    the loop starts, and the same one accompanies every call.
    """
    raw_segments = (
        _FakeRawSegment(start=0.0, end=2.0, text="hello", avg_logprob=math.log(0.9)),
        _FakeRawSegment(start=2.0, end=5.0, text="world", avg_logprob=math.log(0.9)),
    )
    reported: list[tuple[float, float | None]] = []

    segments = build_segments(
        raw_segments, total=10.0, on_progress=lambda done, total: reported.append((done, total))
    )

    assert [segment.text for segment in segments] == ["hello", "world"]
    assert reported == [(2.0, 10.0), (5.0, 10.0)]


def test_build_segments_with_no_reporter_does_not_call_anything() -> None:
    raw_segments = (_FakeRawSegment(start=0.0, end=1.0, text="hi", avg_logprob=math.log(0.9)),)

    segments = build_segments(raw_segments, total=1.0, on_progress=None)

    assert len(segments) == 1


def _write_silence(path: Path, seconds: float = 3.0, frame_rate: int = 16000) -> None:
    """Write a real PCM WAV file with no speech: silence, but audio ffprobe can read."""
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(frame_rate)
        handle.writeframes(b"\x00\x00" * int(frame_rate * seconds))


def _point_settings_at(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    """Make transcribe(), via get_settings(), resolve paths under `data_dir`."""
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(data_dir))
    get_settings.cache_clear()


def _speech_intervals(rttm_path: Path) -> list[tuple[float, float]]:
    """(start, end) pairs from a .rttm's SPEAKER lines: tbeg and tbeg+tdur."""
    intervals = []
    for line in rttm_path.read_text().splitlines():
        if not line.strip():
            continue
        fields = line.split()
        start, duration = float(fields[3]), float(fields[4])
        intervals.append((start, start + duration))
    return intervals


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def _reference_coverage(segments, reference: list[tuple[float, float]]) -> float:
    """Fraction of the reference speech duration overlapped by `segments`.

    Compares timing, not text: the transcribed wording drifts across model
    revisions, the intervals a correct transcript should have found do not.
    """
    reference_total = sum(end - start for start, end in reference)
    covered = sum(_overlap((s.start, s.end), ref) for s in segments for ref in reference)
    return min(covered / reference_total, 1.0)


@pytest.mark.slow  # loads a real Whisper model: ~484 MB on a clean machine
def test_transcribe_produces_no_segments_on_silence(
    tmp_path: Path, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runs always, even in CI: the check that the VAD filter is really on.

    Whisper hallucinates plausible text over silence; a
    generated WAV needs no audio fixture the repository does not have.
    Uses the "low" profile: CI has no GPU and a modest CPU,
    and a test that required "base" would lie to anyone with less hardware.
    """
    _point_settings_at(monkeypatch, tmp_path / "data")
    source = tmp_path / "source" / "silence.wav"
    source.parent.mkdir()
    _write_silence(source)
    recording = import_local_file(db_session, source, get_paths(tmp_path / "data"))

    transcript = transcribe(recording, "low")

    assert transcript.segments == []


def test_transcribe_covers_the_reference_speech_intervals(
    tmp_path: Path, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Integration test on real speech, skipped in CI like the six tests in
    test_eval_set.py. But this material is a loose .wav/.rttm pair, not the
    curated reference.csv corpus the shared eval_dir fixture guards, so this
    test reads VOXTRAMA_EVAL_DIR directly instead of depending on it.
    """
    raw = os.environ.get("VOXTRAMA_EVAL_DIR")
    if not raw:
        pytest.skip("VOXTRAMA_EVAL_DIR is not set: the evaluation set is not available here")
    eval_dir = Path(raw).expanduser()
    source, rttm = eval_dir / "clean-2-it.wav", eval_dir / "clean-2-it.rttm"
    if not source.is_file() or not rttm.is_file():
        pytest.skip(f"{source} or {rttm} not found")

    _point_settings_at(monkeypatch, tmp_path / "data")
    recording = import_local_file(db_session, source, get_paths(tmp_path / "data"))

    transcript = transcribe(recording, "base")

    coverage = _reference_coverage(transcript.segments, _speech_intervals(rttm))
    assert coverage >= 0.85, f"only {coverage:.0%} of the reference speech was covered"
