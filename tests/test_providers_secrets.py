"""Tests for the one rule that has no second chance: the secret never leaves.

Credentials are a secret. Never in the manifest, never
in the logs, never in a tracked file. The logs show the host, never the token.

Kept apart from test_providers_ollama.py because these do not check that the
provider works: they check that it stays quiet about one specific thing, on
every path that carries a URL or a header. A credential reaches the provider
two ways (configured as a secret, or embedded in the URL), and the second
leaks without anyone writing a logging call: providers.http puts the URL it
was given into its message, engine.failure copies that into Run.error, and
from there it reaches the manifest and the progress file.
"""

from __future__ import annotations

from urllib.error import URLError

import pytest
from fakes.http_transport import http_error, install, timeout_error

from voxtrama.providers.base import (
    ProviderCredentialsError,
    ProviderTimeoutError,
    ProviderTransportError,
)
from voxtrama.providers.ollama import OllamaProvider, classify_host


def test_url_with_embedded_credential_yields_a_stripped_host() -> None:
    host, is_local = classify_host("https://user:secret-token@ollama.example.com/")

    assert host == "ollama.example.com"
    assert is_local is False


def test_credential_never_appears_in_an_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = install(monkeypatch)
    transport.route("http://127.0.0.1:11434/api/generate", http_error(401, b"<html>nope</html>"))

    with pytest.raises(ProviderCredentialsError) as excinfo:
        OllamaProvider("http://127.0.0.1:11434", "super-secret-token", 5).generate("prompt", "m")

    assert "super-secret-token" not in str(excinfo.value)
    assert transport.calls[-1].get_header("Authorization") == "Bearer super-secret-token"


# A credential can reach the provider two ways: as a configured secret, which
# the test above covers, or embedded in the URL itself. The second is the one
# that leaks without anybody writing a logging call: providers.http puts the
# URL it was given into its own message, engine.failure copies that message
# into Run.error, and from there it reaches the manifest and the progress
# file. The secrets rule forbids exactly that, so both raises that carry a
# URL are covered here rather than trusted.
_URL_WITH_SECRET = "https://user:url-embedded-secret@ollama.example.com/api/generate"


def test_a_credential_inside_the_url_never_reaches_a_timeout_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = install(monkeypatch)
    transport.route(_URL_WITH_SECRET, timeout_error())
    provider = OllamaProvider("https://user:url-embedded-secret@ollama.example.com", None, 5)

    with pytest.raises(ProviderTimeoutError) as excinfo:
        provider.generate("prompt", "m")

    assert "url-embedded-secret" not in str(excinfo.value)
    assert "ollama.example.com" in str(excinfo.value)


def test_a_credential_inside_the_url_never_reaches_a_transport_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = install(monkeypatch)
    transport.route(_URL_WITH_SECRET, URLError("nodename nor servname provided"))
    provider = OllamaProvider("https://user:url-embedded-secret@ollama.example.com", None, 5)

    with pytest.raises(ProviderTransportError) as excinfo:
        provider.generate("prompt", "m")

    assert "url-embedded-secret" not in str(excinfo.value)
    assert "ollama.example.com" in str(excinfo.value)
