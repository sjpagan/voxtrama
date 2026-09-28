"""Tests for OllamaProvider.measure_generation(): "real speed" is two numbers.

No network: fakes.http_transport, same form as test_providers_ollama.py.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install

from voxtrama.providers.ollama import OllamaProvider


def _generate_ok(body: dict) -> FakeResponse:
    return FakeResponse(200, json.dumps(body).encode())


def test_provider_timings_yield_tokens_per_second_and_load_seconds_apart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real measured numbers on qwen3:4b: 17 tokens in 920312000 ns."""
    transport = install(monkeypatch)
    transport.route(
        "http://127.0.0.1:11434/api/generate",
        _generate_ok(
            {
                "response": "ready",
                "eval_count": 17,
                "eval_duration": 920312000,
                "load_duration": 5580349170,
            }
        ),
    )

    speed = OllamaProvider("http://127.0.0.1:11434", None, 5).measure_generation("qwen3:4b")

    assert speed.source == "provider timings"
    assert speed.tokens == 17
    assert speed.tokens_per_second == pytest.approx(17 / 0.920312, rel=1e-6)
    assert speed.load_seconds == pytest.approx(5.58034917, rel=1e-6)
    assert speed.wall_seconds >= 0


def test_a_provider_that_declares_no_timings_reports_wall_clock_and_no_invented_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never a number reconstructed from the wall clock: say it is not known."""
    transport = install(monkeypatch)
    transport.route("http://127.0.0.1:11434/api/generate", _generate_ok({"response": "ready"}))

    speed = OllamaProvider("http://127.0.0.1:11434", None, 5).measure_generation("m")

    assert speed.source == "wall clock"
    assert speed.tokens is None
    assert speed.tokens_per_second is None
    assert speed.load_seconds is None
    assert speed.wall_seconds >= 0


def test_the_measured_request_is_shaped_like_a_real_run_s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same pair, kept together here too: a rate measured on a request no
    run ever makes is a rate of the wrong thing. The engine's own side of
    this is test_engine_summarize_prompt's
    test_json_output_sets_format_and_think_together_in_the_request.
    """
    transport = install(monkeypatch)
    transport.route("http://127.0.0.1:11434/api/generate", _generate_ok({"response": "ready"}))

    OllamaProvider("http://127.0.0.1:11434", None, 5).measure_generation("m")

    [call] = [c for c in transport.calls if c.full_url.endswith("/api/generate")]
    sent = json.loads(call.data)
    assert sent["format"] == "json"
    assert sent["think"] is False
