"""GET /models: the permanent library: Transcription's three
Whisper profiles, Speakers' own ECAPA-TDNN, and a read-only look at
whatever Ollama exposes, plus the installation summary at the top.
Downloading and removing are their own file, tests/test_web_models_actions.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import voxtrama.api.routes.models as models_route
from voxtrama.setup.download_progress import publish_download_state
from voxtrama.setup.generative_step import GenerativeProviderState
from voxtrama.setup.installation import InstallationConfig, write_installation_config


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def test_the_three_whisper_rows_and_ecapa_show_their_own_licence(client: TestClient) -> None:
    """The test that fails if MIT and Apache-2.0 get swapped, or if a
    single licence stands in for both: the criterion for the row
    ECAPA has never had before.
    """
    body = client.get("/models").text

    assert body.count("MIT licence") == 3
    assert body.count("Apache-2.0 licence") == 1


def test_a_cached_row_shows_installed_and_remove_an_uncached_row_shows_download(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from voxtrama.transcription.asr import weights_for

    base_repo = weights_for("base").repo_id
    monkeypatch.setattr(
        models_route, "is_cached", lambda weights, _models_dir: weights.repo_id == base_repo
    )

    body = client.get("/models").text

    assert 'name="key" value="base"' in body
    assert "Installed" in body
    assert "vx-button--danger vx-button--small" in body
    # "low", "high" and "ecapa" stay uncached: three Download buttons left.
    assert body.count(f'action="{models_route.DOWNLOAD_PATH}"') == 3


def test_removing_the_active_profile_or_ecapa_says_it_will_be_redownloaded(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_installation_config(
        tmp_path, InstallationConfig(hardware_profile="base", cores_per_chunk=4, parallel_chunks=2)
    )
    monkeypatch.setattr(models_route, "is_cached", lambda weights, _models_dir: True)

    body = client.get("/models").text

    # Every row is installed here, but only "base" (the active profile)
    # and "ecapa" (never a profile, always needed) earn the notice.
    # "low" and "high" stay silent about a redownload nobody will trigger.
    assert body.count("downloads it again the next time it is needed") == 2


def test_a_download_in_progress_hides_every_download_button_and_says_so(
    client: TestClient, tmp_path: Path
) -> None:
    publish_download_state(tmp_path, "running", model_label="ASR model medium")

    body = client.get("/models").text

    assert f'action="{models_route.DOWNLOAD_PATH}"' not in body
    assert f'action="{models_route.REMOVE_PATH}"' not in body
    assert "A download is already in progress" in body


def test_ollama_unreachable_still_renders_the_page_with_a_message(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    unreachable = GenerativeProviderState(
        configured=True, reachable=False, host="127.0.0.1:11434", models=()
    )
    monkeypatch.setattr(models_route, "probe_generative_provider", lambda _settings: unreachable)

    response = client.get("/models")

    assert response.status_code == 200
    assert "Ollama is not reachable" in response.text


def test_a_first_run_with_no_installation_config_says_so_and_points_to_setup(
    client: TestClient,
) -> None:
    response = client.get("/models")

    assert response.status_code == 200
    assert "has not been set up yet" in response.text
    assert "/setup/local-processing" in response.text
