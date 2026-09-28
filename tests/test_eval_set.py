"""Guards the private evaluation set against drifting from its reference file."""

from __future__ import annotations

import csv
import wave
from pathlib import Path

EXPECTED_COLUMNS = ["clip", "speakers", "overlap", "language", "duration_s", "notes"]
VALID_OVERLAP = {"yes", "no", ""}
EXPECTED_RATE = 16_000
EXPECTED_CHANNELS = 1
DURATION_TOLERANCE_S = 1.0


def _rows(eval_dir: Path) -> list[dict[str, str]]:
    with (eval_dir / "reference.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_reference_has_the_expected_columns(eval_dir: Path) -> None:
    with (eval_dir / "reference.csv").open(encoding="utf-8", newline="") as handle:
        assert csv.DictReader(handle).fieldnames == EXPECTED_COLUMNS


def test_every_referenced_clip_exists(eval_dir: Path) -> None:
    missing = [r["clip"] for r in _rows(eval_dir) if not (eval_dir / "clips" / r["clip"]).is_file()]
    assert not missing, f"listed in reference.csv but absent from clips/: {missing}"


def test_every_clip_is_referenced(eval_dir: Path) -> None:
    listed = {r["clip"] for r in _rows(eval_dir)}
    present = {p.name for p in (eval_dir / "clips").glob("*.wav")}
    assert not present - listed, (
        f"present in clips/ but absent from reference.csv: {present - listed}"
    )


def test_clips_are_normalised_and_match_their_declared_duration(eval_dir: Path) -> None:
    for row in _rows(eval_dir):
        with wave.open(str(eval_dir / "clips" / row["clip"]), "rb") as audio:
            assert audio.getframerate() == EXPECTED_RATE, row["clip"]
            assert audio.getnchannels() == EXPECTED_CHANNELS, row["clip"]
            seconds = audio.getnframes() / audio.getframerate()
        assert abs(seconds - float(row["duration_s"])) <= DURATION_TOLERANCE_S, row["clip"]


def test_overlap_is_yes_no_or_still_to_be_filled(eval_dir: Path) -> None:
    """Overlapping speech is the case that separates diarisation backends.

    A typo here would silently exclude a clip from the comparison, so the
    column is constrained rather than trusted.
    """
    wrong = {r["clip"]: r["overlap"] for r in _rows(eval_dir) if r["overlap"] not in VALID_OVERLAP}
    assert not wrong, f"overlap must be yes, no or empty: {wrong}"


def test_speakers_is_a_positive_number_once_filled(eval_dir: Path) -> None:
    """An unfilled row is fine. A filled one that is not a count is not."""
    for row in _rows(eval_dir):
        if row["speakers"] == "":
            continue
        assert row["speakers"].isdigit(), f"{row['clip']}: {row['speakers']!r} is not a count"
        assert int(row["speakers"]) >= 1, f"{row['clip']}: at least one person speaks"
