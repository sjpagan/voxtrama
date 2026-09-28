"""Tests for OllamaProvider.probe(): reachable, latency, version, models.

No network: fakes.http_transport replaces urlopen, following the same form
test_providers_ollama.py already uses for generate().
"""

from __future__ import annotations

import json
from urllib.error import URLError

import pytest
from fakes.http_transport import FakeResponse, install

from voxtrama.providers.ollama import OllamaProvider


def _ok(body: dict) -> FakeResponse:
    return FakeResponse(200, json.dumps(body).encode())


def test_probe_of_a_responsive_provider_reports_reachable_version_and_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = install(monkeypatch)
    base = "http://127.0.0.1:11434"
    transport.route(f"{base}/api/version", _ok({"version": "0.34.2"}))
    transport.route(
        f"{base}/api/tags",
        _ok(
            {
                "models": [
                    {"name": "qwen3:4b", "size": 2497293931},
                    {"name": "gemma3:4b", "size": 3338801804},
                ]
            }
        ),
    )

    probe = OllamaProvider(base, None, 5).probe()

    assert probe.reachable is True
    assert probe.error is None
    assert probe.latency_seconds is not None and probe.latency_seconds >= 0
    assert probe.version == "0.34.2"
    assert {model.name for model in probe.models} == {"qwen3:4b", "gemma3:4b"}
    sizes = {model.name: model.size_bytes for model in probe.models}
    assert sizes["qwen3:4b"] == 2497293931


def test_probe_of_a_refused_connection_is_not_reachable_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reason is readable, and doctor never sees an exception."""
    transport = install(monkeypatch)
    transport.route(
        "http://127.0.0.1:11434/api/version", URLError(ConnectionRefusedError("Connection refused"))
    )

    probe = OllamaProvider("http://127.0.0.1:11434", None, 5).probe()

    assert probe.reachable is False
    assert probe.latency_seconds is None
    assert probe.version is None
    assert probe.models == ()
    assert "127.0.0.1:11434" in probe.error


def test_probe_survives_a_working_version_and_a_broken_tags_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A working /api/version earns reachable; a broken /api/tags after it does not undo it."""
    transport = install(monkeypatch)
    base = "http://127.0.0.1:11434"
    transport.route(f"{base}/api/version", _ok({"version": "0.34.2"}))
    transport.route(f"{base}/api/tags", URLError(ConnectionRefusedError("Connection refused")))

    probe = OllamaProvider(base, None, 5).probe()

    assert probe.reachable is True
    assert probe.version == "0.34.2"
    assert probe.models == ()
