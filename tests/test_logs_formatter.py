"""Tests for voxtrama.logs.formatter."""

from __future__ import annotations

import json
import logging

from voxtrama.logs.context import log_context
from voxtrama.logs.formatter import JsonFormatter


def _record(**extra: object) -> logging.LogRecord:
    fields = {"msg": "step finished", "levelname": "INFO", "name": "voxtrama.engine.run"}
    fields.update(extra)
    return logging.makeLogRecord(fields)


def test_core_fields_are_always_present() -> None:
    event = json.loads(JsonFormatter().format(_record()))
    assert event["level"] == "info"
    assert event["logger"] == "voxtrama.engine.run"
    assert event["msg"] == "step finished"
    assert "ts" in event


def test_timestamp_is_utc_iso8601_with_milliseconds() -> None:
    event = json.loads(JsonFormatter().format(_record()))
    assert event["ts"].endswith("Z")
    date_part, time_part = event["ts"][:-1].split("T")
    assert len(date_part.split("-")) == 3
    seconds, millis = time_part.split(".")
    assert len(seconds.split(":")) == 3
    assert len(millis) == 3


def test_known_extra_field_is_kept() -> None:
    event = json.loads(JsonFormatter().format(_record(duration_ms=18422)))
    assert event["duration_ms"] == 18422


def test_unknown_field_is_dropped() -> None:
    event = json.loads(JsonFormatter().format(_record(transcript="hello world")))
    assert "transcript" not in event


def test_line_outside_any_context_has_no_run_id() -> None:
    event = json.loads(JsonFormatter().format(_record()))
    assert "run_id" not in event


def test_line_inside_context_carries_run_id_step_and_job_id() -> None:
    with log_context(run_id="r_7f3a", step="transcribe", job_id="j_1"):
        event = json.loads(JsonFormatter().format(_record()))
    assert event["run_id"] == "r_7f3a"
    assert event["step"] == "transcribe"
    assert event["job_id"] == "j_1"
