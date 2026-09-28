"""POST /setup/private-storage: the file it writes, and the sidebar's
own `Setup` entry, permanent past the first run. GET's own display of
the data directory is the host path when the container knows it, never
`/data`, the mount point only this process sees.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.setup.installation import read_installation_config


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def test_finishing_setup_writes_a_file_that_rereads_to_the_same_values(
    client: TestClient, tmp_path: Path
) -> None:
    posted = client.post(
        "/setup/private-storage",
        data={"hardware_profile": "high", "cores_per_chunk": 6, "parallel_chunks": 2},
        follow_redirects=False,
    )

    assert posted.status_code == 303
    assert posted.headers["location"] == "/"
    config = read_installation_config(tmp_path)
    assert config is not None
    assert config.hardware_profile == "high"
    assert config.cores_per_chunk == 6
    assert config.parallel_chunks == 2
    assert config.instance_token is not None


def test_the_sidebar_still_offers_setup_after_it_is_finished(client: TestClient) -> None:
    # The link's own href, not the ">Setup<" substring: components/
    # sidebar.html wraps every label with its own icon, so the text
    # no longer sits right after the opening tag. The href is also the
    # page the entry leads to (the writable overview, not the wizard's own
    # first step), so asserting on it says more than
    # the label.
    before = client.get("/").text
    assert "/setup" in before

    client.post(
        "/setup/private-storage",
        data={"hardware_profile": "base", "cores_per_chunk": 4, "parallel_chunks": 2},
    )

    # A bar that denies the section the
    # page itself belongs to is worse than an incomplete one. `Setup`
    # stays reachable past the first run, not only before it.
    after = client.get("/").text
    assert "/setup" in after


def test_what_the_wizard_writes_is_what_the_engine_then_reads(
    client: TestClient, tmp_path: Path
) -> None:
    """A regression in one test: a real run died on a model the file named.

    Not a reread of the file (the first test covers that) but of Settings,
    which is what engine.generative and transcription.asr ask,
    built fresh here, the way a worker process builds its own.
    """
    client.post(
        "/setup/private-storage",
        data={
            "hardware_profile": "high",
            "cores_per_chunk": 4,
            "parallel_chunks": 2,
            "ollama_model": "qwen3:4b",
        },
    )

    settings = Settings(data_dir=tmp_path)

    assert settings.ollama_model == "qwen3:4b"
    assert settings.hardware_profile == "high"


def _client_with(settings: Settings, engine: Engine) -> TestClient:
    """A bare TestClient carrying `settings` as-is. build_client always
    builds its own Settings(data_dir=tmp_path), which leaves no way to
    also set host_data_dir for these two tests.
    """

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_the_storage_step_shows_the_host_path_when_the_container_knows_it(
    engine: Engine, tmp_path: Path
) -> None:
    """compose.yaml's VOXTRAMA_HOST_DATA_DIR, not `/data`."""
    settings = Settings(data_dir=tmp_path, host_data_dir="/Users/you/Voxtrama")

    body = _client_with(settings, engine).get("/setup/private-storage").text

    assert "/Users/you/Voxtrama" in body
    assert str(tmp_path) not in body


def test_the_storage_step_falls_back_to_the_container_path_when_unknown(
    engine: Engine, tmp_path: Path
) -> None:
    """No VOXTRAMA_HOST_DATA_DIR (outside the compose file this repo
    ships) is unknown, not a guessed `~/Voxtrama` this process cannot
    verify: settings.data_dir is what shows.
    """
    settings = Settings(data_dir=tmp_path)

    body = _client_with(settings, engine).get("/setup/private-storage").text

    assert str(tmp_path) in body
