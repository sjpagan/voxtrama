"""Configuration problems explained in one line, not in a traceback."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from voxtrama.cli.config_errors import data_dir_problem
from voxtrama.config.settings import Settings


def _settings(data_dir: Path) -> Settings:
    return Settings(data_dir=data_dir)


def test_a_usable_directory_has_no_problem(tmp_path: Path) -> None:
    assert data_dir_problem(_settings(tmp_path)) is None


def test_a_missing_directory_names_the_variable_and_the_fix(tmp_path: Path) -> None:
    """The configuration rule's own example: say what is wrong and what to do about it."""
    message = data_dir_problem(_settings(tmp_path / "absent"))

    assert message is not None
    assert "VOXTRAMA_DATA_DIR" in message
    assert "does not exist" in message
    assert "Create it" in message


def test_a_file_where_a_directory_belongs_says_so(tmp_path: Path) -> None:
    target = tmp_path / "not-a-folder"
    target.write_text("")

    message = data_dir_problem(_settings(target))

    assert message is not None
    assert "is a file, not a directory" in message


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores the permission bits this asserts on",
)
def test_an_unwritable_directory_points_at_doctor(tmp_path: Path) -> None:
    """The fix needs three identities compared, which is doctor's job."""
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        message = data_dir_problem(_settings(locked))
    finally:
        locked.chmod(0o700)

    assert message is not None
    assert "cannot write" in message
    assert "voxtrama doctor" in message
