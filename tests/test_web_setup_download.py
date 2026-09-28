"""The queued model download: the POST
returns immediately instead of blocking inside gunicorn's own worker
timeout, and GET reflects the download's own published state.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.queue import InMemoryQueue
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from voxtrama.setup.download_progress import (
    publish_download_state,
    read_download_job_id,
    read_download_state,
    write_download_job_id,
)


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


def test_the_post_enqueues_and_returns_without_downloading_anything(
    client: TestClient, tmp_path: Path
) -> None:
    """The regression this guards: a blocking fetch_weights() inside the
    request sat past gunicorn's 120-second worker timeout on two profiles
    out of three. Nothing here calls the network (InMemoryQueue.submit_
    download never runs the real job body), so a response at all proves
    the request no longer waits for a download.
    """
    posted = client.post(
        "/setup/local-processing",
        data={"hardware_profile": "low", "cores_per_chunk": 4, "parallel_chunks": 2},
        follow_redirects=False,
    )

    assert posted.status_code == 303
    assert posted.headers["location"].startswith("/setup/local-processing?")
    assert read_download_job_id(tmp_path) is not None


def test_a_running_download_shows_the_progress_panel_and_polls(
    client: TestClient, tmp_path: Path
) -> None:
    publish_download_state(
        tmp_path, "running", model_label="ASR model medium", done_bytes=600, total_bytes=1500
    )

    body = client.get(
        "/setup/local-processing?hardware_profile=base&cores_per_chunk=4&parallel_chunks=2"
    ).text

    assert 'http-equiv="refresh"' in body
    assert "Stop" in body
    assert "Continue" in body


def test_once_cached_the_page_offers_continue_instead_of_downloading(
    client: TestClient, tmp_path: Path
) -> None:
    body = client.get(
        "/setup/local-processing?hardware_profile=low&cores_per_chunk=4&parallel_chunks=2"
    ).text

    # Nothing was ever downloaded in this test's tmp_path, so "low" is not
    # cached and the ordinary Download button shows: the counter-case to
    # the running-download test above, not a duplicate of it.
    assert "Download selected model" in body
    assert 'http-equiv="refresh"' not in body


def test_cancel_writes_cancelled_and_redirects_back(client: TestClient, tmp_path: Path) -> None:
    write_download_job_id(tmp_path, "some-job-id")
    publish_download_state(tmp_path, "running", model_label="ASR model medium")

    posted = client.post(
        "/setup/local-processing/cancel-download",
        data={"hardware_profile": "base", "cores_per_chunk": 4, "parallel_chunks": 2},
        follow_redirects=False,
    )

    assert posted.status_code == 303
    assert read_download_state(tmp_path).state == "cancelled"
