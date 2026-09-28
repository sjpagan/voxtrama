"""Tests for providers.selection: local_only fails before any connection.

The fake here stands for a provider, not a transport: it never opens a
socket by itself, so recording whether it was even constructed is enough
to prove text_provider_for raised before reaching for the network at all.
"""

from __future__ import annotations

import pytest
from fakes.workflow import fake_skill

from voxtrama.providers import selection
from voxtrama.providers.base import PrivacyViolation


class _FakeOllamaProvider:
    """Stands in for OllamaProvider: records whether it was ever built."""

    invoked = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        type(self).invoked = True

    def generate(self, prompt: str, model: str) -> tuple[str, None]:
        raise AssertionError("generate() must never run once local_only has vetoed the call")


@pytest.fixture(autouse=True)
def _fake_ollama_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeOllamaProvider.invoked = False
    monkeypatch.setattr(selection, "OllamaProvider", _FakeOllamaProvider)


def test_local_only_with_a_remote_provider_fails_before_any_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", "https://ollama.example.com")

    with pytest.raises(PrivacyViolation):
        selection.text_provider_for(fake_skill("summarize"))  # LOCAL_ONLY, per fakes.workflow

    assert _FakeOllamaProvider.invoked is False


def test_local_only_with_a_local_provider_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", "http://127.0.0.1:11434")

    provider = selection.text_provider_for(fake_skill("summarize"))

    assert isinstance(provider, _FakeOllamaProvider)
    assert _FakeOllamaProvider.invoked is True
