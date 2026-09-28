"""The clean-up by itself never takes the worker down."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from voxtrama.worker import prune_schedule


def test_a_clean_up_that_fails_is_logged_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _broken(*_args: object) -> None:
        raise RuntimeError("disk gone")

    logged: list[str] = []
    monkeypatch.setattr(prune_schedule, "build_session_factory", _broken)
    monkeypatch.setattr(prune_schedule.logger, "exception", logged.append)

    prune_schedule.prune_once(tmp_path)

    assert logged == ["clean-up failed; trying again tomorrow"]


def test_it_cleans_up_as_soon_as_the_worker_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran = threading.Event()
    monkeypatch.setattr(prune_schedule, "prune_once", lambda _data_dir: ran.set())

    stop = prune_schedule.start_daily_prune(tmp_path)

    assert ran.wait(timeout=5)
    stop.set()
