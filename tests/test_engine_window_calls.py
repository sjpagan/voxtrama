"""The windows of one step sent to the model together, answers kept in order."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import pytest

from voxtrama.engine.context_budget import compute_context_budget
from voxtrama.engine.window_calls import generate_windows
from voxtrama.logs.context import current_context, log_context
from voxtrama.providers.base import GenerationResult, ModelProvenance, ProviderTransportError

PROVENANCE = ModelProvenance("ollama", "127.0.0.1", "m", None, False, False)


class _Slow:
    """Answers each prompt with itself after `delays[prompt]` seconds, counting overlap."""

    def __init__(self, delays: dict[str, float], fail: str | None = None) -> None:
        self.delays, self.fail = delays, fail
        self.sent: list[str] = []
        self.running = self.most = 0
        self.lock = threading.Lock()

    def generate(self, prompt: str, model: str, json_output: bool = False, **_: Any):
        with self.lock:
            self.sent.append(prompt)
            self.running += 1
            self.most = max(self.most, self.running)
        time.sleep(self.delays[prompt])
        with self.lock:
            self.running -= 1
        if prompt == self.fail:
            raise ProviderTransportError("connection refused")
        return GenerationResult(prompt, "stop", 10), PROVENANCE


def _run(provider: _Slow, prompts: list[str], parallel: int, **kwargs: Any):
    budgets = [compute_context_budget(p, 32768) for p in prompts]
    return generate_windows(provider, prompts, "m", budgets, parallel, **kwargs)


def test_answers_come_back_in_window_order_whatever_order_they_finish() -> None:
    provider = _Slow({"w1": 0.3, "w2": 0.0, "w3": 0.1})

    generations = _run(provider, ["w1", "w2", "w3"], parallel=3)

    assert [g.text for g in generations] == ["w1", "w2", "w3"]
    assert provider.most >= 2  # w1 was still running when the others went


def test_the_step_waits_for_the_slowest_window_not_the_sum() -> None:
    provider = _Slow({"w1": 0.3, "w2": 0.3})

    started = time.monotonic()
    _run(provider, ["w1", "w2"], parallel=2)

    assert time.monotonic() - started < 0.5


def test_a_limit_of_one_sends_one_window_at_a_time_as_before() -> None:
    provider = _Slow({"w1": 0.05, "w2": 0.05, "w3": 0.05})

    generations = _run(provider, ["w1", "w2", "w3"], parallel=1)

    assert provider.most == 1
    assert provider.sent == ["w1", "w2", "w3"]
    assert [g.text for g in generations] == ["w1", "w2", "w3"]


def test_a_failing_window_fails_the_step_with_its_own_error() -> None:
    provider = _Slow({"w1": 0.0, "w2": 0.0, "w3": 0.0}, fail="w2")
    failed: list[int] = []

    with pytest.raises(ProviderTransportError, match="connection refused"):
        _run(provider, ["w1", "w2", "w3"], parallel=1, on_failure=failed.append)

    assert failed == [1]
    assert "w3" not in provider.sent  # never asked for text nobody reads


def test_each_window_logs_under_the_step_it_belongs_to(tmp_path) -> None:
    provider = _Slow({"w1": 0.0, "w2": 0.0})
    _run(provider, ["w1", "w2"], parallel=2, cache_dir=tmp_path)
    seen: list[tuple[dict[str, str], str]] = []

    class _Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append((current_context(), record.getMessage()))

    handler = _Keep()
    logger = logging.getLogger("voxtrama.engine.window_calls")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        with log_context(run_id="run-1", step="summarize"):
            _run(provider, ["w1", "w2"], parallel=2, cache_dir=tmp_path)
    finally:
        logger.removeHandler(handler)

    assert len(seen) == 3  # the plan, then one line per window, from its own thread
    assert all(fields == {"run_id": "run-1", "step": "summarize"} for fields, _ in seen)
    assert sorted(m for _, m in seen[1:]) == [
        "Window 1/2: answer kept from an earlier attempt, not asked again",
        "Window 2/2: answer kept from an earlier attempt, not asked again",
    ]


def test_a_retry_asks_only_for_the_windows_not_answered_before(tmp_path) -> None:
    first = _Slow({"w1": 0.0, "w2": 0.0, "w3": 0.0}, fail="w3")
    with pytest.raises(ProviderTransportError):
        _run(first, ["w1", "w2", "w3"], parallel=1, cache_dir=tmp_path)

    again = _Slow({"w1": 0.0, "w2": 0.0, "w3": 0.0})
    generations = _run(again, ["w1", "w2", "w3"], parallel=1, cache_dir=tmp_path)

    assert again.sent == ["w3"]
    assert [g.text for g in generations] == ["w1", "w2", "w3"]


def test_every_answered_window_is_reported() -> None:
    provider = _Slow({"w1": 0.0, "w2": 0.0, "w3": 0.0})
    reports: list[tuple[int, int]] = []

    _run(provider, ["w1", "w2", "w3"], parallel=2, on_answered=lambda d, t: reports.append((d, t)))

    assert reports[0] == (0, 3)
    assert sorted(reports[1:]) == [(1, 3), (2, 3), (3, 3)]
