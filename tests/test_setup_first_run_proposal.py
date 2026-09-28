"""The first result before the tuning, not after four screens.

The machine's proposal is applied and declared (proposal.toml, the home
card), voxtrama.toml is born after the first job with what it used, and
the name is no longer asked before anything else.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.jobs import seed_job
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_queue
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.db.models.run import RunState
from voxtrama.db.models.transcript import Transcript
from voxtrama.setup import proposal as proposal_module
from voxtrama.setup.first_run import settle_after_first_run
from voxtrama.setup.installation import InstallationConfig, write_installation_config
from voxtrama.setup.proposal import Proposal, ensure_proposal, proposal_in_force

PROPOSED = Proposal("low", 3, 2)


@pytest.fixture(autouse=True)
def _this_machine(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(proposal_module, "machine_proposal", lambda data_dir: PROPOSED)
    yield
    get_settings.cache_clear()


def test_a_first_start_writes_the_proposal_and_settings_read_it(tmp_path, monkeypatch) -> None:
    assert ensure_proposal(tmp_path) == PROPOSED

    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    settings = Settings()
    assert (settings.hardware_profile, settings.cores_per_chunk) == ("low", 3)
    assert not (tmp_path / "voxtrama.toml").exists()


def test_voxtrama_toml_wins_and_the_proposal_is_not_written(tmp_path, monkeypatch) -> None:
    write_installation_config(
        tmp_path, InstallationConfig(hardware_profile="high", cores_per_chunk=1, parallel_chunks=1)
    )

    assert ensure_proposal(tmp_path) is None
    assert not (tmp_path / "proposal.toml").exists()
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    assert Settings().hardware_profile == "high"


def test_the_first_succeeded_job_writes_what_it_actually_used(tmp_path, db_session) -> None:
    ensure_proposal(tmp_path)
    run = seed_job(db_session, tmp_path, "first", ["hello"])
    transcript = db_session.scalars(select(Transcript)).one()
    transcript.cpu_threads, transcript.num_workers = 4, 1
    db_session.commit()

    assert settle_after_first_run(db_session, run.id, tmp_path) is True

    written = tomllib.loads((tmp_path / "voxtrama.toml").read_text())
    assert (written["hardware_profile"], written["cores_per_chunk"]) == ("low", 4)
    assert written["parallel_chunks"] == 1
    assert not (tmp_path / "proposal.toml").exists()
    assert proposal_in_force(tmp_path) is None


def test_a_failed_job_writes_nothing(tmp_path, db_session) -> None:
    ensure_proposal(tmp_path)
    run = seed_job(db_session, tmp_path, "broken", ["x"], state=RunState.FAILED)

    assert settle_after_first_run(db_session, run.id, tmp_path) is False
    assert not (tmp_path / "voxtrama.toml").exists()


class _Queue:
    def submit_download(self, key: str) -> str:
        return "job-1"


def _client(tmp_path: Path) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'home.db'}")
    Base.metadata.create_all(engine)

    def _db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = lambda: _Queue()
    return TestClient(app)


def test_the_home_says_what_it_is_using_and_offers_the_download(tmp_path) -> None:
    ensure_proposal(tmp_path)
    body = _client(tmp_path).get("/").text

    assert "Proposed for this machine" in body
    assert "3 cores per chunk" in body and "2 chunks in parallel" in body
    assert 'name="return_to" value="/"' in body
    assert "Download the transcription model" in body


def test_the_download_starts_from_home_and_comes_back_home(tmp_path) -> None:
    ensure_proposal(tmp_path)
    posted = _client(tmp_path).post(
        "/setup/local-processing",
        data={
            "hardware_profile": "low",
            "cores_per_chunk": 3,
            "parallel_chunks": 2,
            "return_to": "/",
        },
        follow_redirects=False,
    )

    assert posted.status_code == 303
    assert posted.headers["location"] == "/#vx-first-run"


def test_once_voxtrama_toml_exists_the_card_is_gone(tmp_path) -> None:
    write_installation_config(
        tmp_path, InstallationConfig(hardware_profile="low", cores_per_chunk=1, parallel_chunks=1)
    )

    assert "Proposed for this machine" not in _client(tmp_path).get("/").text
