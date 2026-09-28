"""Tests for the NDJSON streaming path added to OllamaProvider.generate().

No network: fakes.http_transport, same form as test_providers_ollama.py.
FakeResponse.readline() hands back one routed line at a time, the same
shape a real streamed /api/generate response takes. Log lines are read with
fakes.log_capture.capture_logger, not `caplog`. See that module's own
docstring for why.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, http_error, install
from fakes.log_capture import capture_logger

from voxtrama.providers.base import ProviderCredentialsError
from voxtrama.providers.ollama import OllamaProvider
from voxtrama.providers.ollama_call_log import PROGRESS_CHARS_STEP

CALL_LOG_LOGGER = "voxtrama.providers.ollama_call_log"


def _stream(*lines: dict) -> FakeResponse:
    body = b"\n".join(json.dumps(line).encode() for line in lines)
    return FakeResponse(200, body)


def _fragment_lines(
    fragment: str, count: int, done_reason: str, prompt_eval_count: int
) -> list[dict]:
    """`count` lines each carrying one copy of `fragment`, the last one marked done."""
    lines = [{"response": fragment, "done": False} for _ in range(count - 1)]
    lines.append(
        {
            "response": fragment,
            "done": True,
            "done_reason": done_reason,
            "prompt_eval_count": prompt_eval_count,
        }
    )
    return lines


def test_a_long_generation_logs_more_than_one_progress_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The terminal panel gets an advancing line, not silence."""
    transport = install(monkeypatch)
    fragment = "x" * (PROGRESS_CHARS_STEP // 2)
    lines = _fragment_lines(fragment, count=10, done_reason="stop", prompt_eval_count=42)
    transport.route("http://127.0.0.1:11434/api/generate", _stream(*lines))
    transport.route("http://127.0.0.1:11434/api/tags", FakeResponse(200, b'{"models": []}'))

    with capture_logger(CALL_LOG_LOGGER) as records:
        OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")

    progress_lines = [r for r in records if "words so far" in r.getMessage()]
    assert len(progress_lines) > 1


def test_fragments_are_reassembled_exactly_like_a_single_body_would_be(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = install(monkeypatch)
    lines = [
        {"response": "Once upon ", "done": False},
        {"response": "a time, ", "done": False},
        {"response": "the end.", "done": True, "done_reason": "stop", "prompt_eval_count": 10},
    ]
    transport.route("http://127.0.0.1:11434/api/generate", _stream(*lines))
    transport.route("http://127.0.0.1:11434/api/tags", FakeResponse(200, b'{"models": []}'))

    result, _ = OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")

    assert result.text == "Once upon a time, the end."


def test_prompt_eval_count_reaches_the_final_log_line_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = install(monkeypatch)
    lines = [{"response": "hi", "done": True, "done_reason": "stop", "prompt_eval_count": 512}]
    transport.route("http://127.0.0.1:11434/api/generate", _stream(*lines))
    transport.route("http://127.0.0.1:11434/api/tags", FakeResponse(200, b'{"models": []}'))

    with capture_logger(CALL_LOG_LOGGER) as records:
        result, _ = OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")

    assert result.prompt_eval_count == 512
    [done_line] = [r for r in records if " done, ~" in r.getMessage()]
    assert done_line.count == 512


def test_prompt_eval_count_is_not_invented_when_ollama_omits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = install(monkeypatch)
    lines = [{"response": "hi", "done": True, "done_reason": "stop"}]
    transport.route("http://127.0.0.1:11434/api/generate", _stream(*lines))
    transport.route("http://127.0.0.1:11434/api/tags", FakeResponse(200, b'{"models": []}'))

    with capture_logger(CALL_LOG_LOGGER) as records:
        result, _ = OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")

    assert result.prompt_eval_count is None
    [done_line] = [r for r in records if " done, ~" in r.getMessage()]
    assert not hasattr(done_line, "count")


def test_no_log_line_carries_the_generated_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only quantities may leave the process, never the text itself."""
    transport = install(monkeypatch)
    secret = "S3CR3T " * (PROGRESS_CHARS_STEP // 7 + 5)
    lines = _fragment_lines(secret, count=5, done_reason="stop", prompt_eval_count=7)
    transport.route("http://127.0.0.1:11434/api/generate", _stream(*lines))
    transport.route("http://127.0.0.1:11434/api/tags", FakeResponse(200, b'{"models": []}'))

    with capture_logger(CALL_LOG_LOGGER) as records:
        OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")

    assert len(records) > 0
    assert all("S3CR3T" not in r.getMessage() for r in records)


def test_a_non_200_status_is_still_classified_through_the_streaming_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The status arrives before any NDJSON line does, and is never itself streamed."""
    transport = install(monkeypatch)
    transport.route(
        "http://127.0.0.1:11434/api/generate", http_error(401, b"<!DOCTYPE html><body>nope</body>")
    )

    with pytest.raises(ProviderCredentialsError):
        OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")
