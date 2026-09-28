"""POST /models/download and POST /models/remove: the same core
calls the guided setup's own step 2 already uses
(queue.submit_download, weights.remove_weights), reached through the
library's own two thin routes instead of a `return_to` field.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.queue import InMemoryQueue
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from voxtrama.api.routes.models import weight_set_for
from voxtrama.setup.download_progress import (
    publish_download_state,
    read_download_job_id,
    read_download_state,
)
from voxtrama.weights import ECAPA_KEY


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def queue() -> InMemoryQueue:
    return InMemoryQueue()


@pytest.fixture
def client(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, queue: InMemoryQueue
) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch, queue=queue)


def _cache_dir(tmp_path: Path, key: str) -> Path:
    weights = weight_set_for(key)
    return tmp_path / "models" / ("models--" + weights.repo_id.replace("/", "--"))


def test_download_enqueues_and_redirects_back_to_the_library(
    client: TestClient, tmp_path: Path
) -> None:
    posted = client.post("/models/download", data={"key": "low"}, follow_redirects=False)

    assert posted.status_code == 303
    assert posted.headers["location"] == "/models"
    assert read_download_job_id(tmp_path) is not None


def test_download_accepts_the_ecapa_key_the_same_way(client: TestClient, tmp_path: Path) -> None:
    posted = client.post("/models/download", data={"key": ECAPA_KEY}, follow_redirects=False)

    assert posted.status_code == 303
    assert read_download_state(tmp_path).activity.name == "speaker model ECAPA-TDNN"


def test_an_unknown_key_is_rejected_without_touching_anything(
    client: TestClient, tmp_path: Path
) -> None:
    posted = client.post("/models/download", data={"key": "ultra"}, follow_redirects=False)

    assert posted.status_code == 303
    assert read_download_job_id(tmp_path) is None


def test_a_download_already_in_progress_blocks_a_second_one(
    client: TestClient, tmp_path: Path
) -> None:
    publish_download_state(tmp_path, "running", model_label="ASR model small")

    client.post("/models/download", data={"key": "base"}, follow_redirects=False)

    assert read_download_state(tmp_path).activity.name == "ASR model small"


def test_removing_a_cached_model_drops_its_cache_and_redirects_back(
    client: TestClient, tmp_path: Path
) -> None:
    cache_dir = _cache_dir(tmp_path, "low")
    cache_dir.mkdir(parents=True)

    posted = client.post("/models/remove", data={"key": "low"}, follow_redirects=False)

    assert posted.status_code == 303
    assert posted.headers["location"] == "/models"
    assert not cache_dir.exists()


def test_removing_ecapa_works_the_same_way_as_a_profile(client: TestClient, tmp_path: Path) -> None:
    cache_dir = _cache_dir(tmp_path, ECAPA_KEY)
    cache_dir.mkdir(parents=True)

    client.post("/models/remove", data={"key": ECAPA_KEY}, follow_redirects=False)

    assert not cache_dir.exists()


def test_a_download_in_progress_blocks_removal_too(client: TestClient, tmp_path: Path) -> None:
    cache_dir = _cache_dir(tmp_path, "low")
    cache_dir.mkdir(parents=True)
    publish_download_state(tmp_path, "running", model_label="ASR model small")

    client.post("/models/remove", data={"key": "low"}, follow_redirects=False)

    assert cache_dir.exists()
