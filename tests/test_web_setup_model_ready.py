"""GET /setup/model-ready: an Ollama that does not answer, one
found at the standard address, and the step's own query-string proposal.
Licence rendering and preselection are their own files
(tests/test_web_setup_model_licences.py, tests/test_web_setup_model_preselection.py),
split out to stay under the project's file cap, same as
tests/test_web_setup_local_processing.py was for this one.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.ollama_provider import fake_ollama_provider, reachable_probe, stub_model_facts
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import voxtrama.api.routes.setup_models as setup_models_route
import voxtrama.setup.generative_step as generative_step
from voxtrama.providers.ollama_show import ModelFacts
from voxtrama.providers.probe import ProviderProbe


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def test_ollama_absent_at_the_default_address_proceeds_without_blocking(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing configured *and* nothing at the standard
    address: the wizard still proceeds, the
    same "not configured" message as before, not a stall on the probe.
    """
    unreachable = ProviderProbe(
        reachable=False, latency_seconds=None, version=None, models=(), error="refused"
    )
    monkeypatch.setattr(generative_step, "OllamaProvider", fake_ollama_provider(unreachable))

    response = client.get("/setup/model-ready")

    assert response.status_code == 200
    assert "Ollama is not configured" in response.text
    assert "Skip (no generative model)" in response.text


def test_ollama_reachable_at_the_default_address_is_found_without_configuration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An Ollama already running needs no VOXTRAMA_OLLAMA_URL
    to be seen: the standard address is tried, and its models listed.
    """
    monkeypatch.setattr(
        generative_step,
        "OllamaProvider",
        fake_ollama_provider(reachable_probe("qwen3:30b-a3b-instruct")),
    )
    # Step 3 now also reads this model's licence from /api/show,
    # stubbed rather than routed through a fake transport, since this test
    # is about the address being found, not about a licence.
    stub_model_facts(
        monkeypatch,
        generative_step,
        {"qwen3:30b-a3b-instruct": ModelFacts(context_length=None, licence_text="MIT License")},
    )

    response = client.get("/setup/model-ready")

    assert response.status_code == 200
    assert "localhost:11434" in response.text
    assert "qwen3:30b-a3b-instruct" in response.text


def test_ollama_unreachable_does_not_block_the_step(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from voxtrama.setup.generative_step import GenerativeProviderState

    unreachable = GenerativeProviderState(
        configured=True, reachable=False, host="127.0.0.1:11434", models=()
    )
    monkeypatch.setattr(
        setup_models_route, "probe_generative_provider", lambda _settings: unreachable
    )

    response = client.get("/setup/model-ready")

    assert response.status_code == 200
    assert "Skip (no generative model)" in response.text


def test_model_ready_opened_bare_proposes_the_machines_own_tuning_not_one_core(
    client: TestClient,
) -> None:
    """No query string must not silently pin cores_per_chunk=1: the case
    nobody tries by hand, since every link this app renders already carries the
    query string forward. apple-silicon.yaml proposes 2 chunks of 4 cores, and
    this machine's 36 GiB recommends "high" (diagnostics.advice.advise_profile),
    never the fixed "base" the old default hid behind. Asserted on the "Skip"
    link's own carried query string, which renders whether or not Ollama answers.
    """
    body = client.get("/setup/model-ready").text

    assert (
        "/setup/private-storage?hardware_profile=high&amp;cores_per_chunk=4&amp;parallel_chunks=2"
        in body
    )


def test_model_ready_keeps_explicit_query_values_over_the_proposal(client: TestClient) -> None:
    body = client.get(
        "/setup/model-ready",
        params={"hardware_profile": "low", "cores_per_chunk": 2, "parallel_chunks": 1},
    ).text

    assert (
        "/setup/private-storage?hardware_profile=low&amp;cores_per_chunk=2&amp;parallel_chunks=1"
        in body
    )
