"""GET /setup/model-ready: the proposed model is the first installed
one with a permissive licence, never a hard-coded name,
exercised with made-up ones. Asterisk/text rendering is
tests/test_web_setup_model_licences.py, split out to stay under the
project's 150-line file limit.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.ollama_provider import fake_ollama_provider, reachable_probe, stub_model_facts
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import voxtrama.setup.generative_step as generative_step
from voxtrama.providers.ollama_show import ModelFacts


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def test_preselects_the_first_installed_model_with_a_permissive_licence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No `qwen3` here. The rule is exercised with made-up names,
    the constrained one listed first, the same ordering the real
    machine happens to have."""
    monkeypatch.setattr(
        generative_step,
        "OllamaProvider",
        fake_ollama_provider(reachable_probe("model-a", "model-b")),
    )
    calls = stub_model_facts(
        monkeypatch,
        generative_step,
        {
            "model-a": ModelFacts(context_length=4096, licence_text="Gemma Terms of Use"),
            "model-b": ModelFacts(context_length=8192, licence_text="MIT License"),
        },
    )

    body = client.get("/setup/model-ready").text

    assert 'name="ollama_model" value="model-b"' in body
    # One /api/show read per listed model, never a second one for the
    # model that also ends up selected.
    assert calls == ["model-a", "model-b"]


def test_preselects_nothing_when_every_installed_model_is_constrained(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generative_step,
        "OllamaProvider",
        fake_ollama_provider(reachable_probe("model-a", "model-b")),
    )
    stub_model_facts(
        monkeypatch,
        generative_step,
        {
            "model-a": ModelFacts(context_length=4096, licence_text="Gemma Terms of Use"),
            "model-b": ModelFacts(context_length=8192, licence_text="LLAMA 3 COMMUNITY LICENSE"),
        },
    )

    body = client.get("/setup/model-ready").text

    assert "Context window" not in body
    assert "Skip (no generative model)" in body


def test_an_explicit_model_wins_even_when_it_is_constrained(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generative_step,
        "OllamaProvider",
        fake_ollama_provider(reachable_probe("model-a", "model-b")),
    )
    stub_model_facts(
        monkeypatch,
        generative_step,
        {
            "model-a": ModelFacts(context_length=4096, licence_text="Gemma Terms of Use"),
            "model-b": ModelFacts(context_length=8192, licence_text="MIT License"),
        },
    )

    body = client.get("/setup/model-ready", params={"model": "model-a"}).text

    assert 'name="ollama_model" value="model-a"' in body
