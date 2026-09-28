"""GET /setup/model-ready: a licence per installed model,
and the asterisk it earns when that licence is not permissive. Preselection
is tests/test_web_setup_model_preselection.py, split out to stay under
the project's file cap.
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


def test_a_permissive_licence_carries_no_asterisk(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generative_step, "OllamaProvider", fake_ollama_provider(reachable_probe("model-a"))
    )
    stub_model_facts(
        monkeypatch,
        generative_step,
        {"model-a": ModelFacts(context_length=4096, licence_text="Apache License\nVersion 2.0")},
    )

    body = client.get("/setup/model-ready").text

    assert "vx-licence-flag" not in body


def test_a_recognised_non_permissive_licence_carries_the_asterisk_and_its_own_text(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generative_step, "OllamaProvider", fake_ollama_provider(reachable_probe("model-a"))
    )
    stub_model_facts(
        monkeypatch,
        generative_step,
        {
            "model-a": ModelFacts(
                context_length=4096, licence_text="Gemma Terms of Use\nLast modified: ..."
            )
        },
    )

    body = client.get("/setup/model-ready").text

    assert "vx-licence-flag" in body
    assert "Gemma Terms of Use" in body
    assert "licence not recognised" not in body


def test_an_unrecognised_licence_still_carries_the_asterisk(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case that decides the rule: unknown takes
    the asterisk, never a silent green light."""
    monkeypatch.setattr(
        generative_step, "OllamaProvider", fake_ollama_provider(reachable_probe("model-a"))
    )
    stub_model_facts(
        monkeypatch,
        generative_step,
        {"model-a": ModelFacts(context_length=4096, licence_text="Ozelot Public Licence 3.1")},
    )

    body = client.get("/setup/model-ready").text

    assert "vx-licence-flag" in body
    assert "licence not recognised" in body
    assert "Ozelot Public Licence 3.1" in body


def test_a_failed_read_shows_licence_unknown_and_still_renders(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generative_step, "OllamaProvider", fake_ollama_provider(reachable_probe("model-a"))
    )
    stub_model_facts(
        monkeypatch,
        generative_step,
        {"model-a": ModelFacts(context_length=None, licence_text=None)},
    )

    response = client.get("/setup/model-ready")

    assert response.status_code == 200
    assert "vx-licence-flag" in response.text
    assert "licence unknown" in response.text
