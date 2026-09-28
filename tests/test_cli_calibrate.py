"""`voxtrama calibrate`, through the CLI: every case exits 0, naming its real cause.

Never measures (that is another command's job), so these tests only check
that the command names what it found, or what is missing and why, and
that it never fails on an optional folder.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from typer.testing import CliRunner

from voxtrama.cli.main import app

runner = CliRunner()
REFERENCE_COLUMNS = ["clip", "speakers", "overlap", "language", "duration_s", "notes"]


def _write_reference(eval_dir: Path, rows: list[dict[str, str]]) -> None:
    with (eval_dir / "reference.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REFERENCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_without_an_eval_dir_it_names_the_material_and_the_doc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The test that counts: exactly how CI runs it, VOXTRAMA_EVAL_DIR unset."""
    monkeypatch.delenv("VOXTRAMA_EVAL_DIR", raising=False)

    result = runner.invoke(app, ["calibrate"])

    assert result.exit_code == 0
    assert "VOXTRAMA_EVAL_DIR is not set" in result.output
    assert "docs/evaluation-set.md" in result.output


def test_an_eval_dir_pointing_nowhere_says_the_path_does_not_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "nowhere"
    monkeypatch.setenv("VOXTRAMA_EVAL_DIR", str(missing))

    result = runner.invoke(app, ["calibrate"])

    assert result.exit_code == 0
    assert str(missing) in result.output
    assert "does not exist" in result.output


def test_a_folder_with_no_reference_csv_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_EVAL_DIR", str(tmp_path))

    result = runner.invoke(app, ["calibrate"])

    assert result.exit_code == 0
    assert "No reference.csv here yet" in result.output


def test_a_malformed_reference_csv_names_the_expected_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "reference.csv").write_text("clip,notes\nmeeting-01.wav,\n")
    monkeypatch.setenv("VOXTRAMA_EVAL_DIR", str(tmp_path))

    result = runner.invoke(app, ["calibrate"])

    assert result.exit_code == 0
    assert "does not have the expected columns" in result.output
    assert "speakers" in result.output


def test_a_curated_corpus_with_no_annotations_says_what_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    monkeypatch.setenv("VOXTRAMA_EVAL_DIR", str(tmp_path))

    result = runner.invoke(app, ["calibrate"])

    assert result.exit_code == 0
    assert "meeting-01.wav" in result.output
    assert "annotation: no" in result.output


def test_an_annotated_corpus_reports_the_material_without_measuring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    (tmp_path / "clips" / "meeting-01.annotation.yaml").write_text("clip: meeting-01.wav\n")
    (tmp_path / "REVISION").write_text("2026-09-23\n")
    monkeypatch.setenv("VOXTRAMA_EVAL_DIR", str(tmp_path))

    result = runner.invoke(app, ["calibrate"])

    assert result.exit_code == 0
    assert "annotated:    1 of 1" in result.output
    assert "2026-09-23" in result.output
    assert "does not measure extraction" in result.output
    assert "--run" in result.output
