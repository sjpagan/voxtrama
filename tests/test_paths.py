"""Tests for voxtrama.config.paths."""

from __future__ import annotations

from pathlib import Path

from voxtrama.config.paths import default_data_dir, get_paths


def test_paths_derive_from_data_dir(tmp_path: Path) -> None:
    paths = get_paths(tmp_path)
    assert paths.data_dir == tmp_path
    assert paths.recordings_dir == tmp_path / "recordings"
    assert paths.runs_dir == tmp_path / "runs"
    assert paths.models_dir == tmp_path / "models"
    assert paths.logs_dir == tmp_path / "logs"
    assert paths.db_path == tmp_path / "voxtrama.db"


def test_paths_change_with_data_dir(tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    assert get_paths(other).recordings_dir == other / "recordings"


def test_default_data_dir_is_absolute_and_named_voxtrama() -> None:
    result = default_data_dir()
    assert result.is_absolute()
    assert result.name == "voxtrama"
