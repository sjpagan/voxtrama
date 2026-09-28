"""voxtrama.calibration.dataset.DatasetStatus: every way eval_dir can fail to offer a
ready corpus, each with its own status rather than one collapsed boolean.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.calibration.dataset import DatasetStatus, read_dataset


def test_an_unset_eval_dir_is_its_own_status() -> None:
    report = read_dataset(None)

    assert report.status == DatasetStatus.UNSET
    assert report.eval_dir is None


def test_a_path_that_does_not_exist_is_its_own_status(tmp_path: Path) -> None:
    missing = tmp_path / "nowhere"

    report = read_dataset(missing)

    assert report.status == DatasetStatus.DIRECTORY_MISSING
    assert report.eval_dir == missing


def test_a_folder_with_no_reference_csv_is_its_own_status(tmp_path: Path) -> None:
    report = read_dataset(tmp_path)

    assert report.status == DatasetStatus.REFERENCE_MISSING


def test_a_reference_csv_with_the_wrong_columns_is_its_own_status(tmp_path: Path) -> None:
    (tmp_path / "reference.csv").write_text("clip,notes\nmeeting-01.wav,\n")

    report = read_dataset(tmp_path)

    assert report.status == DatasetStatus.REFERENCE_MALFORMED
    assert report.reference_columns == ("clip", "notes")
    assert report.clips == ()


def test_a_well_formed_but_empty_reference_csv_is_ready(tmp_path: Path) -> None:
    (tmp_path / "clips").mkdir()
    (tmp_path / "reference.csv").write_text("clip,speakers,overlap,language,duration_s,notes\n")

    report = read_dataset(tmp_path)

    assert report.status == DatasetStatus.READY
    assert report.clips == ()
