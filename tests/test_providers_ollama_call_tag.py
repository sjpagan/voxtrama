"""The Ollama call's log lines say which window they belong to."""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install
from fakes.log_capture import capture_logger

from voxtrama.providers.ollama import OllamaProvider
from voxtrama.providers.ollama_call_log import CALL_TAG

CALL_LOG_LOGGER = "voxtrama.providers.ollama_call_log"


def _stream(*lines: dict) -> FakeResponse:
    return FakeResponse(200, b"\n".join(json.dumps(line).encode() for line in lines))


def test_a_tagged_call_says_which_window_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lines name the window they belong to, one window each."""
    transport = install(monkeypatch)
    lines = [{"response": "hi there", "done": True, "done_reason": "stop"}]
    transport.route("http://127.0.0.1:11434/api/generate", _stream(*lines))
    transport.route("http://127.0.0.1:11434/api/tags", FakeResponse(200, b'{"models": []}'))

    token = CALL_TAG.set("Window 2/3")
    try:
        with capture_logger(CALL_LOG_LOGGER) as records:
            OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")
    finally:
        CALL_TAG.reset(token)

    messages = [r.getMessage() for r in records]
    assert messages[0].startswith("Window 2/3: sent to m, prompt 6 characters")
    assert any(m.startswith("Window 2/3: m done, ~2 words in ") for m in messages)
