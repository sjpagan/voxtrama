"""Tests for providers.ollama_generation: options forwarded, done_reason and prompt_eval_count read.

Split from test_providers_ollama.py, which already covers status handling
and locality, so neither file grows past the project's size limit. The
context-budget half of the contract gets its own file, same as ollama_generation.py
itself split out of ollama.py.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install

from voxtrama.providers.ollama import OllamaProvider


def _ok(body: dict) -> FakeResponse:
    return FakeResponse(200, json.dumps(body).encode())


def test_options_are_forwarded_unchanged_into_the_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """num_ctx is never the server's own default, always ours."""
    transport = install(monkeypatch)
    transport.route("http://127.0.0.1:11434/api/generate", _ok({"response": "hi"}))
    transport.route("http://127.0.0.1:11434/api/tags", _ok({"models": []}))

    OllamaProvider("http://127.0.0.1:11434", None, 5).generate(
        "prompt", "m", options={"num_ctx": 16384}
    )

    sent = json.loads(transport.calls[0].data)
    assert sent["options"] == {"num_ctx": 16384}


def test_no_options_means_no_options_key_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller that passes nothing must not silently opt into a server default either."""
    transport = install(monkeypatch)
    transport.route("http://127.0.0.1:11434/api/generate", _ok({"response": "hi"}))
    transport.route("http://127.0.0.1:11434/api/tags", _ok({"models": []}))

    OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")

    sent = json.loads(transport.calls[0].data)
    assert "options" not in sent


@pytest.mark.parametrize(
    ("body", "expected_done_reason", "expected_prompt_eval_count"),
    [
        ({"response": "hi", "done_reason": "stop", "prompt_eval_count": 2050}, "stop", 2050),
        ({"response": "hi", "done_reason": "length", "prompt_eval_count": 7059}, "length", 7059),
        # Wrong types are read as unknown, never crashed on or coerced.
        ({"response": "hi", "done_reason": 1, "prompt_eval_count": "many"}, None, None),
    ],
)
def test_done_reason_and_prompt_eval_count_are_read_from_the_body(
    monkeypatch: pytest.MonkeyPatch,
    body: dict,
    expected_done_reason: str | None,
    expected_prompt_eval_count: int | None,
) -> None:
    """The two facts the input/output truncation checks rely on."""
    transport = install(monkeypatch)
    transport.route("http://127.0.0.1:11434/api/generate", _ok(body))
    transport.route("http://127.0.0.1:11434/api/tags", _ok({"models": []}))

    result, _ = OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")

    assert result.done_reason == expected_done_reason
    assert result.prompt_eval_count == expected_prompt_eval_count
