"""An opt-in test against a real Ollama server.

Follows the same shape as tests/conftest.py's eval_dir fixture: skip on a
missing environment variable rather than fail, so the suite stays green on
a machine with no such server reachable. Green here does not mean
"verified against a real provider", only "not disproven by one".
"""

from __future__ import annotations

import os

import pytest

from voxtrama.providers.ollama import OllamaProvider

DEFAULT_MODEL = "qwen2.5:0.5b"


def test_generate_against_a_real_ollama_server() -> None:
    url = os.environ.get("VOXTRAMA_OLLAMA_URL")
    if not url:
        pytest.skip("VOXTRAMA_OLLAMA_URL is not set: no real Ollama to test against")
    model = os.environ.get("VOXTRAMA_OLLAMA_MODEL", DEFAULT_MODEL)
    auth = os.environ.get("VOXTRAMA_OLLAMA_AUTH")

    provider = OllamaProvider(url, auth, timeout=60)
    result, provenance = provider.generate("Reply with the single word: ok.", model)

    assert result.text
    assert provenance.model == model
    assert provenance.host
