"""GET /setup/local-processing: the one scenario that must not
depend on the machine running the suite: Apple Silicon's own tuning,
and a machine short on space. /setup/model-ready's own tests are
tests/test_web_setup_model_ready.py, split out to stay under the project's
file cap.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.setup_client import APPLE_SILICON, build_client, build_engine, short_on_space
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import voxtrama.api.routes.setup_processing as setup_processing_route


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def test_apple_silicon_shows_the_machine_as_unified_and_picks_its_own_tuning(
    client: TestClient,
) -> None:
    body = client.get("/setup/local-processing").text

    assert "Apple M3 Pro" in body
    assert "36 GB unified" in body
    # apple-silicon.yaml's own proposal: 2 parallel chunks, 4 cores each.
    assert 'name="parallel_chunks" value="2"' in body
    assert 'name="cores_per_chunk" value="4"' in body


def test_a_profile_that_does_not_fit_free_disk_shows_disabled_with_the_reason(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    low_bytes = 484 * 1024 * 1024
    tight = short_on_space(APPLE_SILICON, low_bytes + 1024)
    monkeypatch.setattr(setup_processing_route, "read_machine", lambda _dir: tight)

    body = client.get("/setup/local-processing").text

    assert "vx-profile-card--disabled" in body
    # The high (large-v3) and base (medium) profiles both exceed what fits;
    # their card shows the reason instead of a pick link.
    assert "Needs" in body and "free" in body
