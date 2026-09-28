"""setup.finish.installation_config_from_choices's own merge-not-replace
rule for model_context_limits, split out of test_setup_finish.py to stay
under the project's 150-line file cap.
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


def test_saving_a_second_model_keeps_the_first_models_measured_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """model_context_limits is a mapping across every model ever measured,
    not the single model this call happens to be saving: a save must merge
    into what read_installation_config already found, not replace it, or
    picking the earlier model again falls back to FALLBACK_MAX_CTX in silence.
    """
    settings = Settings(data_dir=tmp_path)
    write_installation_config(
        tmp_path,
        InstallationConfig(
            hardware_profile="base",
            cores_per_chunk=4,
            parallel_chunks=2,
            model_context_limits={"qwen3:4b": 262144},
        ),
    )
    transport = install(monkeypatch)
    transport.route(
        f"{DEFAULT_OLLAMA_URL}/api/show",
        FakeResponse(
            200,
            json.dumps(
                {"model_info": {"general.architecture": "gemma3", "gemma3.context_length": 131072}}
            ).encode(),
        ),
    )

    config = installation_config_from_choices(
        settings, **_choices(ollama_model="gemma3:4b", context_limit=131072)
    )

    assert config.model_context_limits == {"qwen3:4b": 262144, "gemma3:4b": 131072}


def test_no_model_chosen_keeps_the_ceilings_already_measured(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    write_installation_config(
        tmp_path,
        InstallationConfig(
            hardware_profile="base",
            cores_per_chunk=4,
            parallel_chunks=2,
            model_context_limits={"qwen3:4b": 262144},
        ),
    )

    config = installation_config_from_choices(settings, **_choices())

    assert config.model_context_limits == {"qwen3:4b": 262144}
