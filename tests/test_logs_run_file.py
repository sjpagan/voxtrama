"""Tests for voxtrama.logs.run_file."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from voxtrama.logs.context import log_context
from voxtrama.logs.formatter import JsonFormatter
from voxtrama.logs.run_file import RunFileHandler


def _record() -> logging.LogRecord:
    return logging.makeLogRecord({"msg": "step finished", "levelname": "INFO", "name": "x"})


def _handler(runs_dir: Path) -> RunFileHandler:
    handler = RunFileHandler(runs_dir)
    handler.setFormatter(JsonFormatter())
    return handler


def test_line_with_run_id_is_appended_under_its_run_folder(tmp_path: Path) -> None:
    handler = _handler(tmp_path)
    with log_context(run_id="r_7f3a"):
        handler.emit(_record())

    log_file = tmp_path / "r_7f3a" / "run.log"
    assert log_file.is_file()
    event = json.loads(log_file.read_text().splitlines()[0])
    assert event["run_id"] == "r_7f3a"


def test_line_without_run_id_is_not_written_anywhere(tmp_path: Path) -> None:
    handler = _handler(tmp_path)
    handler.emit(_record())
    assert list(tmp_path.iterdir()) == []


def test_run_folder_is_created_if_missing(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    handler = _handler(runs_dir)
    with log_context(run_id="r_new"):
        handler.emit(_record())
    assert (runs_dir / "r_new" / "run.log").is_file()


def test_write_failure_does_not_raise(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")  # runs_dir itself is a file: mkdir must fail
    handler = _handler(blocked)
    with log_context(run_id="r_7f3a"):
        handler.emit(_record())  # must not raise


def test_two_runs_append_to_separate_files(tmp_path: Path) -> None:
    handler = _handler(tmp_path)
    with log_context(run_id="r_1"):
        handler.emit(_record())
    with log_context(run_id="r_2"):
        handler.emit(_record())
    assert (tmp_path / "r_1" / "run.log").is_file()
    assert (tmp_path / "r_2" / "run.log").is_file()
