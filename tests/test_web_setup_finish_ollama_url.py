"""POST /setup/private-storage: the address it writes doubles as
the one providers.selection.text_provider_for can use afterwards.

Split from test_web_setup_finish.py to stay under the project's 150-line file
cap. That file already carries the token and Settings-reread coverage.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.setup_client import build_client, build_engine
from fakes.workflow import fake_skill
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from voxtrama.config.settings import get_settings
from voxtrama.providers.ollama import OllamaProvider
from voxtrama.providers.selection import text_provider_for
from voxtrama.setup.generative_step import DEFAULT_OLLAMA_URL
from voxtrama.setup.installation import installation_config_path


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def _post_with_a_chosen_model(client: TestClient) -> None:
    client.post(
        "/setup/private-storage",
        data={
            "hardware_profile": "high",
            "cores_per_chunk": 4,
            "parallel_chunks": 2,
            "ollama_model": "qwen3:4b",
        },
    )


def test_the_toml_file_carries_the_address_a_chosen_model_came_from(
    client: TestClient, tmp_path: Path
) -> None:
    """No VOXTRAMA_OLLAMA_URL configured, so the standard address
    (the one step 3 listed "qwen3:4b" from) is what gets written.
    """
    _post_with_a_chosen_model(client)

    toml_text = installation_config_path(tmp_path).read_text()

    assert f'ollama_url = "{DEFAULT_OLLAMA_URL}"' in toml_text


def test_a_model_chosen_by_the_wizard_is_enough_for_the_engine_to_find_a_provider(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real run died on VOXTRAMA_OLLAMA_URL not being
    set. The guided setup's own file is now enough,
    no environment variable required.

    classify_host(DEFAULT_OLLAMA_URL) reads as local (checked directly), so
    LOCAL_ONLY never raises PrivacyViolation here: only
    ProviderNotConfiguredError was ever in question. text_provider_for does
    no I/O, so this needs no fake transport either.
    """
    _post_with_a_chosen_model(client)
    # text_provider_for reads the process-wide get_settings(), not the
    # TestClient's own dependency override. Pointing it at the same data
    # directory the POST just wrote to is what makes it see the file.
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    provider = text_provider_for(fake_skill("summarize"))

    assert isinstance(provider, OllamaProvider)
