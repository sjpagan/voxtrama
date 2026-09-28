"""GET /models: the download progress panel, split from
tests/test_web_models.py to stay under the project's file cap. A gigabyte
download used to leave this page immobile until reloaded by hand; these
are the criteria that guard against it coming back.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from voxtrama.setup.download_progress import publish_download_state


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def test_a_running_download_shows_the_model_the_bytes_and_polls(
    client: TestClient, tmp_path: Path
) -> None:
    publish_download_state(
        tmp_path, "running", model_label="ASR model medium", done_bytes=600, total_bytes=1500
    )

    body = client.get("/models").text

    assert 'http-equiv="refresh"' in body
    assert "ASR model medium" in body
    assert "width: 40%" in body


def test_a_finished_download_stops_polling(client: TestClient, tmp_path: Path) -> None:
    publish_download_state(tmp_path, "succeeded", model_label="ASR model medium")

    body = client.get("/models").text

    assert 'http-equiv="refresh"' not in body


def test_a_failed_download_says_so(client: TestClient, tmp_path: Path) -> None:
    publish_download_state(
        tmp_path, "failed", model_label="ASR model medium", message="disk is full"
    )

    body = client.get("/models").text

    assert 'http-equiv="refresh"' not in body
    assert "The download failed" in body
    assert "disk is full" in body


def test_a_download_started_from_step_2_shows_up_here_too(
    client: TestClient, tmp_path: Path
) -> None:
    """The slot is one for the whole installation:
    a download the wizard's own step 2 enqueued has to appear here while
    it runs, not only on the page that started it.
    """
    posted = client.post(
        "/setup/local-processing",
        data={"hardware_profile": "base", "cores_per_chunk": 4, "parallel_chunks": 2},
        follow_redirects=False,
    )
    assert posted.status_code == 303

    body = client.get("/models").text

    assert 'http-equiv="refresh"' in body
    assert "ASR model medium" in body
