"""providers.ollama_show: /api/show's own context_length and licence
fields, read together.

No network: fakes.http_transport replaces urlopen, same as
test_providers_ollama_probe.py.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install, timeout_error

from voxtrama.providers.ollama_show import read_model_facts


def _ok(body: dict) -> FakeResponse:
    return FakeResponse(200, json.dumps(body).encode())


def test_reads_the_architecture_prefixed_context_length(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = install(monkeypatch)
    transport.route(
        "http://127.0.0.1:11434/api/show",
        _ok({"model_info": {"general.architecture": "qwen3", "qwen3.context_length": 262144}}),
    )

    facts = read_model_facts("http://127.0.0.1:11434", "127.0.0.1:11434", "qwen3:4b", {}, 5)

    assert facts.context_length == 262144
    assert len(transport.calls) == 1


def test_a_different_architecture_reads_its_own_prefixed_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = install(monkeypatch)
    transport.route(
        "http://127.0.0.1:11434/api/show",
        _ok({"model_info": {"general.architecture": "gemma3", "gemma3.context_length": 131072}}),
    )

    facts = read_model_facts("http://127.0.0.1:11434", "127.0.0.1:11434", "gemma3:4b", {}, 5)

    assert facts.context_length == 131072


def test_an_unreachable_host_reads_as_unknown_not_a_raised_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch).route("http://127.0.0.1:11434/api/show", timeout_error())

    facts = read_model_facts("http://127.0.0.1:11434", "127.0.0.1:11434", "qwen3:4b", {}, 5)

    assert facts.context_length is None
    assert facts.licence_text is None


def test_a_body_missing_model_info_reads_as_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch).route("http://127.0.0.1:11434/api/show", _ok({}))

    facts = read_model_facts("http://127.0.0.1:11434", "127.0.0.1:11434", "qwen3:4b", {}, 5)

    assert facts.context_length is None
    assert facts.licence_text is None


def test_the_same_read_carries_the_licence_text_alongside_context_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One request, two facts: never asked twice."""
    transport = install(monkeypatch)
    transport.route(
        "http://127.0.0.1:11434/api/show",
        _ok(
            {
                "model_info": {"general.architecture": "qwen3", "qwen3.context_length": 262144},
                "license": "Apache License\nVersion 2.0, January 2004",
            }
        ),
    )

    facts = read_model_facts("http://127.0.0.1:11434", "127.0.0.1:11434", "qwen3:4b", {}, 5)

    assert facts.context_length == 262144
    assert facts.licence_text == "Apache License\nVersion 2.0, January 2004"
    assert len(transport.calls) == 1


def test_a_non_string_licence_field_reads_as_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch).route("http://127.0.0.1:11434/api/show", _ok({"license": None}))

    facts = read_model_facts("http://127.0.0.1:11434", "127.0.0.1:11434", "qwen3:4b", {}, 5)

    assert facts.licence_text is None
