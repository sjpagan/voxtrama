"""GET and POST /setup/private-storage's own defaults: a bare visit
(no query string, the case nobody tries by hand) must propose this machine's
own tuning, never the fixed hardware_profile="base"/cores_per_chunk=1 that
used to sit there unannounced. Split from test_web_setup_finish.py to stay
under the project's 150-line file cap.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.setup_client import build_client, build_engine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from voxtrama.setup.installation import read_installation_config


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    return build_engine(tmp_path)


@pytest.fixture
def client(engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from build_client(engine, tmp_path, monkeypatch)


def test_private_storage_opened_bare_proposes_the_machines_own_tuning_not_one_core(
    client: TestClient,
) -> None:
    """apple-silicon.yaml proposes 2 chunks of 4 cores, and this machine's 36
    GiB recommends "high" (diagnostics.advice.advise_profile), never the
    fixed "base" the old default hid behind.
    """
    body = client.get("/setup/private-storage").text

    assert 'name="hardware_profile" value="high"' in body
    assert 'name="cores_per_chunk" value="4"' in body
    assert 'name="parallel_chunks" value="1"' not in body
    assert 'name="parallel_chunks" value="2"' in body
    assert "Maximum accuracy · whisper-large-v3" in body
    assert "2 chunks × 4 cores" in body


def test_private_storage_keeps_explicit_query_values_over_the_proposal(client: TestClient) -> None:
    body = client.get(
        "/setup/private-storage",
        params={"hardware_profile": "low", "cores_per_chunk": 2, "parallel_chunks": 1},
    ).text

    assert 'name="hardware_profile" value="low"' in body
    assert 'name="cores_per_chunk" value="2"' in body
    assert 'name="parallel_chunks" value="1"' in body


def test_finishing_setup_from_a_bare_visit_writes_the_machines_own_proposal(
    client: TestClient, tmp_path: Path
) -> None:
    """The hidden fields a bare GET renders (previous test) are what a
    real "Finish setup" click posts back, asserted by reading the file it
    writes, not just the page that offers it.
    """
    page = client.get("/setup/private-storage")
    assert 'name="cores_per_chunk" value="4"' in page.text

    posted = client.post(
        "/setup/private-storage",
        data={"hardware_profile": "high", "cores_per_chunk": 4, "parallel_chunks": 2},
        follow_redirects=False,
    )

    assert posted.status_code == 303
    config = read_installation_config(tmp_path)
    assert config is not None
    assert config.hardware_profile == "high"
    assert config.cores_per_chunk == 4
    assert config.parallel_chunks == 2


def test_finishing_setup_with_no_fields_at_all_still_writes_the_machines_own_proposal(
    client: TestClient, tmp_path: Path
) -> None:
    """The POST is the function that *writes* the file, so its own defaults
    matter more than the GET's, not less.

    The form always carries the three resolved values, so this shape does not
    happen by clicking, which is why it went unnoticed: the fields
    defaulted to hardware_profile="base"/1/1 and a request that simply omitted
    them wrote a one-core machine to disk with nothing said.
    """
    posted = client.post("/setup/private-storage", data={}, follow_redirects=False)

    assert posted.status_code == 303
    config = read_installation_config(tmp_path)
    assert config is not None
    assert config.cores_per_chunk == 4
    assert config.parallel_chunks == 2
    assert config.hardware_profile == "high"
