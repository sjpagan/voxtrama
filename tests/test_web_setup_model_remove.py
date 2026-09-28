"""POST /setup/local-processing/remove-model ("I can download and
delete the library"). Removes a model's cache from disk, independent of
which profile is selected and never while a download is in flight.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from voxtrama.setup.download_progress import publish_download_state
from voxtrama.transcription.asr import weights_for


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def _cache_dir(tmp_path: Path, profile: str) -> Path:
    weights = weights_for(profile)
    return tmp_path / "models" / ("models--" + weights.repo_id.replace("/", "--"))


def test_removes_the_cached_model_and_redirects_back(client: TestClient, tmp_path: Path) -> None:
    cache_dir = _cache_dir(tmp_path, "low")
    cache_dir.mkdir(parents=True)

    posted = client.post(
        "/setup/local-processing/remove-model",
        data={"hardware_profile": "low", "cores_per_chunk": 4, "parallel_chunks": 2},
        follow_redirects=False,
    )

    assert posted.status_code == 303
    assert posted.headers["location"].startswith("/setup/local-processing?")
    assert not cache_dir.exists()


def test_a_download_in_progress_blocks_the_removal(client: TestClient, tmp_path: Path) -> None:
    """The cache a running download might still be writing into must not
    be cleaned out from under it.
    """
    cache_dir = _cache_dir(tmp_path, "low")
    cache_dir.mkdir(parents=True)
    publish_download_state(tmp_path, "running", model_label="ASR model small")

    posted = client.post(
        "/setup/local-processing/remove-model",
        data={"hardware_profile": "low", "cores_per_chunk": 4, "parallel_chunks": 2},
        follow_redirects=False,
    )

    assert posted.status_code == 303
    assert cache_dir.exists()


def test_an_unknown_profile_is_rejected_like_the_download_post(client: TestClient) -> None:
    posted = client.post(
        "/setup/local-processing/remove-model",
        data={"hardware_profile": "ultra", "cores_per_chunk": 4, "parallel_chunks": 2},
        follow_redirects=False,
    )

    assert posted.status_code == 303
    assert "error=unavailable" in posted.headers["location"]
