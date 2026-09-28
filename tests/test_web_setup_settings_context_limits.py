"""GET and POST /setup: each of the page's forms carries the context
limit of the model it actually names, not of whatever model `?model=`
happens to be previewing. Split out of test_web_setup_settings.py to stay
under the project's 150-line file cap.
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
from voxtrama.setup.installation import (
    InstallationConfig,
    read_installation_config,
    write_installation_config,
)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def _write_config(tmp_path: Path, **overrides: object) -> InstallationConfig:
    fields: dict[str, object] = {
        "hardware_profile": "high",
        "cores_per_chunk": 4,
        "parallel_chunks": 2,
        "instance_token": "a-token",
        **overrides,
    }
    config = InstallationConfig(**fields)
    write_installation_config(tmp_path, config)
    return config


def _stub_both_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        generative_step,
        "OllamaProvider",
        fake_ollama_provider(reachable_probe("qwen3:4b", "gemma3:4b")),
    )
    stub_model_facts(
        monkeypatch,
        generative_step,
        {
            "qwen3:4b": ModelFacts(context_length=262144, licence_text="Apache License 2.0"),
            "gemma3:4b": ModelFacts(context_length=131072, licence_text="Gemma Terms of Use"),
        },
    )


def test_the_profile_form_does_not_carry_the_context_limit_of_a_previewed_model(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """qwen3:4b is configured, with its own measured ceiling. Landing on
    `?model=gemma3:4b` only previews gemma3:4b's licence and ceiling; the
    "Change profile" form still names qwen3:4b (it is not choosing a
    model) and must not smuggle gemma3:4b's own context_length in as a
    hidden field, or saving the profile would overwrite qwen3:4b's ceiling
    with a number measured for a different model.
    """
    _write_config(tmp_path, ollama_model="qwen3:4b", model_context_limits={"qwen3:4b": 262144})
    _stub_both_models(monkeypatch)

    body = client.get("/setup?model=gemma3:4b").text
    profile_form = body.split("Change profile")[1].split("Change parallelism")[0]

    assert "context_limit" not in profile_form


def test_saving_the_profile_while_previewing_another_model_keeps_the_configured_models_own_ceiling(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same preview as above, but through the POST the fixed form now
    sends: no context_limit field at all. qwen3:4b's own 262144 must
    survive, never overwritten by gemma3:4b's 131072 this render happened
    to show.
    """
    _write_config(tmp_path, ollama_model="qwen3:4b", model_context_limits={"qwen3:4b": 262144})
    _stub_both_models(monkeypatch)
    client.get("/setup?model=gemma3:4b")

    client.post(
        "/setup",
        data={
            "hardware_profile": "low",
            "cores_per_chunk": 4,
            "parallel_chunks": 2,
            "ollama_model": "qwen3:4b",
        },
    )

    config = read_installation_config(tmp_path)
    assert config is not None
    assert config.model_context_limits == {"qwen3:4b": 262144}
