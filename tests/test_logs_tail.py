"""Tests for voxtrama.logs.tail: reading a run's own run.log for the run page's panel."""

from __future__ import annotations

import json
from pathlib import Path

from voxtrama.logs.tail import RunLogTail, tail_lines_with_offset


def tail_lines(path, limit):
    return tail_lines_with_offset(path, limit)[0]


def _line(ts: str, msg: str, logger: str = "voxtrama.engine.run") -> str:
    return json.dumps({"ts": ts, "level": "info", "logger": logger, "msg": msg})


def test_tail_lines_formats_ts_and_msg_into_hh_mm_ss(tmp_path: Path) -> None:
    path = tmp_path / "run.log"
    path.write_text(_line("2026-09-25T23:31:49.123Z", "Starting run") + "\n")

    assert tail_lines(path, limit=10) == ["23:31:49  Starting run"]


def test_tail_lines_keeps_only_the_last_n(tmp_path: Path) -> None:
    path = tmp_path / "run.log"
    ts = "2026-09-25T00:00:00.000Z"
    path.write_text("".join(_line(ts, f"line {i}") + "\n" for i in range(5)))

    lines = tail_lines(path, limit=2)

    assert lines == ["00:00:00  line 3", "00:00:00  line 4"]


def test_tail_lines_skips_malformed_and_incomplete_lines(tmp_path: Path) -> None:
    path = tmp_path / "run.log"
    path.write_text("not json\n" + json.dumps({"ts": "2026-09-25T00:00:00.000Z"}) + "\n")

    assert tail_lines(path, limit=10) == []


def test_tail_lines_on_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert tail_lines(tmp_path / "no-such.log", limit=10) == []


def test_tail_lines_drops_lines_from_a_third_party_logger(tmp_path: Path) -> None:
    path = tmp_path / "run.log"
    ts = "2026-09-25T00:00:00.000Z"
    path.write_text(
        _line(ts, "HTTP Request: GET https://huggingface.co/api/...", logger="httpx")
        + "\n"
        + _line(ts, "step started", logger="voxtrama.engine.preparation")
        + "\n"
    )

    assert tail_lines(path, limit=10) == ["00:00:00  step started"]


def test_run_log_tail_reads_only_new_lines_since_the_last_call(tmp_path: Path) -> None:
    path = tmp_path / "run.log"
    path.write_text(_line("2026-09-25T00:00:00.000Z", "first") + "\n")
    tail = RunLogTail(path)
    assert tail.read_new_lines() == ["00:00:00  first"]

    with path.open("a") as handle:
        handle.write(_line("2026-09-25T00:00:01.000Z", "second") + "\n")

    assert tail.read_new_lines() == ["00:00:01  second"]
    # Nothing new since the last read: an empty poll, not a repeat.
    assert tail.read_new_lines() == []


def test_run_log_tail_holds_back_a_line_still_being_written(tmp_path: Path) -> None:
    """A read caught between the writer's own write() and the trailing "\\n" must not
    show a half line. It waits for the newline instead of guessing at it."""
    path = tmp_path / "run.log"
    path.write_text(_line("2026-09-25T00:00:00.000Z", "whole") + "\n")
    partial = _line("2026-09-25T00:00:01.000Z", "not yet")[:10]
    with path.open("a") as handle:
        handle.write(partial)  # no trailing newline: still being written

    tail = RunLogTail(path)
    assert tail.read_new_lines() == ["00:00:00  whole"]

    with path.open("a") as handle:
        handle.write(_line("2026-09-25T00:00:01.000Z", "not yet")[10:] + "\n")

    assert tail.read_new_lines() == ["00:00:01  not yet"]


def test_run_log_tail_on_a_file_that_does_not_exist_yet_is_empty(tmp_path: Path) -> None:
    tail = RunLogTail(tmp_path / "no-such.log")
    assert tail.read_new_lines() == []


def test_run_log_tail_drops_lines_from_a_third_party_logger(tmp_path: Path) -> None:
    path = tmp_path / "run.log"
    ts = "2026-09-25T00:00:00.000Z"
    path.write_text(_line(ts, "resolve-cache/models/...", logger="huggingface_hub") + "\n")
    tail = RunLogTail(path)

    assert tail.read_new_lines() == []

    with path.open("a") as handle:
        handle.write(_line(ts, "step finished", logger="voxtrama.engine.preparation") + "\n")

    assert tail.read_new_lines() == ["00:00:00  step finished"]
