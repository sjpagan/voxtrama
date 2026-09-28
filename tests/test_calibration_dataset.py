"""What voxtrama.calibration.dataset reports about a ready curated corpus.

DatasetStatus's own cases (unset, missing directory, missing or malformed
reference.csv) live in tests/test_calibration_dataset_status.py. This file
only covers what a READY corpus reports about its clips and its revision.
"""

from __future__ import annotations

import csv
from pathlib import Path

from voxtrama.calibration.dataset import DatasetStatus, read_dataset

REFERENCE_COLUMNS = ["clip", "speakers", "overlap", "language", "duration_s", "notes"]


def _write_reference(eval_dir: Path, rows: list[dict[str, str]]) -> None:
    with (eval_dir / "reference.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REFERENCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_a_curated_corpus_lists_its_clips_and_what_is_missing(tmp_path: Path) -> None:
    (tmp_path / "clips").mkdir()
    _write_reference(
        tmp_path,
        [
            {
                "clip": "meeting-01.wav",
                "speakers": "2",
                "overlap": "no",
                "language": "it",
                "duration_s": "12.0",
                "notes": "",
            }
        ],
    )
    (tmp_path / "clips" / "meeting-01.wav").write_bytes(b"")

    report = read_dataset(tmp_path)

    assert report.status == DatasetStatus.READY
    assert len(report.clips) == 1
    clip = report.clips[0]
    assert clip.clip == "meeting-01.wav"
    assert clip.has_clip
    assert not clip.has_annotation
    assert report.annotated == ()


def test_a_row_whose_clip_file_is_missing_is_reported_as_such(tmp_path: Path) -> None:
    (tmp_path / "clips").mkdir()
    _write_reference(
        tmp_path,
        [
            {
                "clip": "gone.wav",
                "speakers": "",
                "overlap": "",
                "language": "it",
                "duration_s": "1.0",
                "notes": "",
            }
        ],
    )

    report = read_dataset(tmp_path)

    assert not report.clips[0].has_clip


def test_an_annotated_clip_is_reported_as_such(tmp_path: Path) -> None:
    (tmp_path / "clips").mkdir()
    _write_reference(
        tmp_path,
        [
            {
                "clip": "meeting-01.wav",
                "speakers": "",
                "overlap": "",
                "language": "it",
                "duration_s": "1.0",
                "notes": "",
            }
        ],
    )
    (tmp_path / "clips" / "meeting-01.wav").write_bytes(b"")
    (tmp_path / "clips" / "meeting-01.annotation.yaml").write_text("clip: meeting-01.wav\n")

    report = read_dataset(tmp_path)

    assert len(report.annotated) == 1
    assert report.annotated[0].clip == "meeting-01.wav"


def test_the_declared_revision_is_read_and_stripped(tmp_path: Path) -> None:
    (tmp_path / "clips").mkdir()
    _write_reference(tmp_path, [])
    (tmp_path / "REVISION").write_text("2026-09-23\n")

    report = read_dataset(tmp_path)

    assert report.revision == "2026-09-23"


def test_no_revision_file_reports_none(tmp_path: Path) -> None:
    (tmp_path / "clips").mkdir()
    _write_reference(tmp_path, [])

    report = read_dataset(tmp_path)

    assert report.revision is None
