"""Tests for providers.ollama: status read before the body, host derives locality.

No network: fakes.http_transport replaces urlopen, so every case here is the
exact status/body combination the specification's evidence describes,
reproduced without needing the real provider that produced it.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, http_error, install, timeout_error

from voxtrama.providers.base import (
    ModelProvenance,
    ProviderCredentialsError,
    ProviderModelNotFoundError,
    ProviderTimeoutError,
)
from voxtrama.providers.ollama import OllamaProvider


def _ok(body: dict) -> FakeResponse:
    return FakeResponse(200, json.dumps(body).encode())


@pytest.mark.parametrize(
    ("host", "port", "expect_remote"),
    [
        ("127.0.0.1", 11434, False),
        ("host.docker.internal", 11434, False),
        ("ollama.example.com", 443, True),
    ],
)
def test_generate_derives_local_or_remote_from_the_url(
    monkeypatch: pytest.MonkeyPatch, host: str, port: int, expect_remote: bool
) -> None:
    transport = install(monkeypatch)
    base = f"http://{host}:{port}"
    transport.route(f"{base}/api/generate", _ok({"response": "hi"}))
    transport.route(f"{base}/api/tags", _ok({"models": [{"name": "m", "digest": "sha256:x"}]}))

    result, provenance = OllamaProvider(base, None, 5).generate("prompt", "m")

    assert result.text == "hi"
    assert provenance == ModelProvenance(
        provider="ollama",
        host=f"{host}:{port}",
        model="m",
        fingerprint="sha256:x",
        remote=expect_remote,
        profile_check_skipped=expect_remote,
    )


def test_401_with_html_body_names_credentials_not_a_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact case seen in practice: 401, answered in HTML."""
    transport = install(monkeypatch)
    transport.route(
        "https://ai.example.com/api/generate", http_error(401, b"<!DOCTYPE html><body>nope</body>")
    )

    with pytest.raises(ProviderCredentialsError) as excinfo:
        OllamaProvider("https://ai.example.com", None, 5).generate("prompt", "m")

    assert "ai.example.com" in str(excinfo.value)
    assert "<!DOCTYPE" not in str(excinfo.value)


def test_404_names_the_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = install(monkeypatch)
    transport.route("http://127.0.0.1:11434/api/generate", http_error(404, b"not found"))

    with pytest.raises(ProviderModelNotFoundError) as excinfo:
        OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "phi3")

    assert "phi3" in str(excinfo.value)


def test_a_timeout_raises_provider_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = install(monkeypatch)
    transport.route("http://127.0.0.1:11434/api/generate", timeout_error())

    with pytest.raises(ProviderTimeoutError):
        OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")


@pytest.mark.parametrize(
    "tags_body",
    [
        {"models": [{"name": "other-model", "digest": "sha256:zzz"}]},
        {"models": [{"name": "m"}]},
    ],
)
def test_fingerprint_absent_from_tags_is_none_not_the_tag(
    monkeypatch: pytest.MonkeyPatch, tags_body: dict
) -> None:
    transport = install(monkeypatch)
    transport.route("http://127.0.0.1:11434/api/generate", _ok({"response": "hi"}))
    transport.route("http://127.0.0.1:11434/api/tags", _ok(tags_body))

    result, provenance = OllamaProvider("http://127.0.0.1:11434", None, 5).generate("prompt", "m")

    assert provenance.fingerprint is None
    assert provenance.model == "m"
    assert result.done_reason is None
    assert result.prompt_eval_count is None
