"""Dry-run tests for generate.py: no ElevenLabs call is ever made here.

Every case in cases.yaml is checked against its own RTTM ground truth: the
segment count, the overlap it declares (or doesn't), and the final wav's
duration must all agree with the timeline generate.py built the audio from.
"""

from __future__ import annotations

from pathlib import Path

import generate
import pytest

pytestmark = pytest.mark.skipif(not generate.ffmpeg_available(), reason="ffmpeg is not installed")

FIXTURES_DIR = Path(__file__).resolve().parent
CASES = generate.load_cases(FIXTURES_DIR / "cases.yaml")
VOICES = generate.load_voices(FIXTURES_DIR / "voices.yaml")


def _parse_rttm(path: Path) -> list[tuple[str, float, float]]:
    """Return (speaker, start, duration) for every SPEAKER line in an RTTM file."""
    segments = []
    for line in path.read_text().splitlines():
        fields = line.split()
        speaker, start, duration = fields[7], float(fields[3]), float(fields[4])
        segments.append((speaker, start, duration))
    return segments


def _overlap_seconds(a: tuple[str, float, float], b: tuple[str, float, float]) -> float:
    _, a_start, a_dur = a
    _, b_start, b_dur = b
    a_end, b_end = a_start + a_dur, b_start + b_dur
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_case_generates_without_error(case: generate.Case, tmp_path: Path) -> None:
    wav_path = generate.generate_case(case, VOICES, tmp_path, dry_run=True)
    assert wav_path.is_file()
    assert (tmp_path / f"{case.id}.rttm").is_file()
    assert (tmp_path / f"{case.id}.json").is_file()


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_rttm_matches_plan(case: generate.Case, tmp_path: Path) -> None:
    generate.generate_case(case, VOICES, tmp_path, dry_run=True)
    segments = _parse_rttm(tmp_path / f"{case.id}.rttm")

    assert len(segments) == len(case.turns)
    assert all(duration > 0 for _, _, duration in segments)
    assert {speaker for speaker, _, _ in segments} == {turn.voice for turn in case.turns}
    assert len({speaker for speaker, _, _ in segments}) == case.speakers


def test_overlap_15_has_overlap_in_expected_range(tmp_path: Path) -> None:
    case = next(c for c in CASES if c.id == "overlap-15")
    generate.generate_case(case, VOICES, tmp_path, dry_run=True)
    segments = _parse_rttm(tmp_path / f"{case.id}.rttm")

    total_duration = max(start + duration for _, start, duration in segments)
    overlaps = [_overlap_seconds(segments[i], segments[i + 1]) for i in range(len(segments) - 1)]
    overlap_total = sum(overlaps)

    assert any(overlap > 0 for overlap in overlaps)
    fraction = overlap_total / total_duration
    assert 0.10 <= fraction <= 0.20


@pytest.mark.parametrize(
    "case",
    [c for c in CASES if not any(turn.overlap_ms for turn in c.turns)],
    ids=[c.id for c in CASES if not any(turn.overlap_ms for turn in c.turns)],
)
def test_cases_without_overlap_have_no_overlapping_segments(
    case: generate.Case, tmp_path: Path
) -> None:
    generate.generate_case(case, VOICES, tmp_path, dry_run=True)
    segments = _parse_rttm(tmp_path / f"{case.id}.rttm")

    for i in range(len(segments) - 1):
        # ffmpeg's millisecond rounding of the RTTM timestamps can leave a
        # sub-millisecond sliver. Only a real overlap should fail this.
        assert _overlap_seconds(segments[i], segments[i + 1]) <= 0.002


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_wav_duration_matches_last_segment_end(case: generate.Case, tmp_path: Path) -> None:
    wav_path = generate.generate_case(case, VOICES, tmp_path, dry_run=True)
    segments = _parse_rttm(tmp_path / f"{case.id}.rttm")

    wav_duration = generate._wav_duration(wav_path)
    last_segment_end = max(start + duration for _, start, duration in segments)
    assert abs(wav_duration - last_segment_end) <= 0.1
