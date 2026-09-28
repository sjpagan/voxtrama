"""setup.finish.installation_config_from_choices: what POST /setup/private-storage
writes, without going through the HTTP route or a real Ollama.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fakes.http_transport import FakeResponse, install
from fakes.setup_client import APPLE_SILICON

import voxtrama.setup.step_defaults as step_defaults
from voxtrama.config.settings import Settings
from voxtrama.setup.finish import installation_config_from_choices
from voxtrama.setup.generative_step import DEFAULT_OLLAMA_URL
from voxtrama.setup.installation import InstallationConfig, write_installation_config


@pytest.fixture(autouse=True)
def _fixed_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    # resolve_step_defaults reads the real machine otherwise. Pinned to
    # APPLE_SILICON the same way fakes.setup_client's own TestClient is,
    # so cores_per_chunk/parallel_chunks do not vary with whatever runs
    # this suite.
    monkeypatch.setattr(step_defaults, "read_machine", lambda _dir: APPLE_SILICON)


def _choices(**overrides: object) -> dict[str, object]:
    fields = {
        "hardware_profile": "base",
        "cores_per_chunk": None,
        "parallel_chunks": None,
        "ollama_model": None,
        "context_limit": None,
    }
    fields.update(overrides)
    return fields


def test_a_chosen_model_writes_the_standard_address_when_nothing_is_configured(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path)

    config = installation_config_from_choices(settings, **_choices(ollama_model="qwen3:4b"))

    assert config.ollama_url == DEFAULT_OLLAMA_URL


def test_a_configured_address_is_written_as_is_not_the_default(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, ollama_url="http://ollama.example:11434")

    config = installation_config_from_choices(settings, **_choices(ollama_model="qwen3:4b"))

    assert config.ollama_url == "http://ollama.example:11434"


def test_no_model_chosen_writes_no_address_even_when_one_is_configured(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, ollama_url="http://ollama.example:11434")

    config = installation_config_from_choices(settings, **_choices())

    assert config.ollama_url is None


def test_an_existing_token_survives_a_second_call(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    write_installation_config(
        tmp_path,
        InstallationConfig(
            hardware_profile="base", cores_per_chunk=4, parallel_chunks=2, instance_token="a-token"
        ),
    )

    config = installation_config_from_choices(settings, **_choices())

    assert config.instance_token == "a-token"


def test_a_context_limit_above_the_models_own_ceiling_is_clamped_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)
    transport = install(monkeypatch)
    transport.route(
        f"{DEFAULT_OLLAMA_URL}/api/show",
        FakeResponse(
            200,
            json.dumps(
                {"model_info": {"general.architecture": "qwen3", "qwen3.context_length": 32768}}
            ).encode(),
        ),
    )

    config = installation_config_from_choices(
        settings, **_choices(ollama_model="qwen3:4b", context_limit=131072)
    )

    assert config.model_context_limits == {"qwen3:4b": 32768}
