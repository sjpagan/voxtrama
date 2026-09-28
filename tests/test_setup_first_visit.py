"""A first visit opens the guided setup.

Until voxtrama.toml exists or the setup is skipped once, the home page
sends the browser to the first step. Skipping keeps the machine's
proposal in force and goes to the new-job form, which then stays there.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.setup import proposal as proposal_module
from voxtrama.setup.installation import InstallationConfig, write_installation_config
from voxtrama.setup.proposal import Proposal

pytestmark = pytest.mark.first_visit


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(proposal_module, "machine_proposal", lambda data_dir: Proposal("low", 2, 1))
    engine = create_engine(f"sqlite:///{tmp_path / 'home.db'}")
    Base.metadata.create_all(engine)

    def _db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    yield TestClient(app, follow_redirects=False)
    get_settings.cache_clear()


def test_a_first_visit_goes_to_the_guided_setup(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 303
    assert response.headers["location"] == "/setup/local-processing"


def test_the_first_step_offers_to_skip_and_skipping_stays_skipped(client: TestClient) -> None:
    step = client.get("/setup/local-processing").text
    assert 'formaction="/setup/skip"' in step

    skipped = client.post("/setup/skip")

    assert skipped.headers["location"] == "/"
    assert client.get("/").status_code == 200
    assert 'formaction="/setup/skip"' not in client.get("/setup/local-processing").text


def test_a_finished_setup_never_redirects(client: TestClient, tmp_path: Path) -> None:
    write_installation_config(
        tmp_path, InstallationConfig(hardware_profile="low", cores_per_chunk=2, parallel_chunks=1)
    )

    assert client.get("/").status_code == 200
