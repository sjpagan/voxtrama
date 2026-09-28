"""Settings › Data & privacy: where the data lives and what leaves."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.config.providers import ProviderConfig
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base
from voxtrama.rendering.data_privacy import LEAVES, LOCAL_SERVER, privacy_view
from voxtrama.setup.installation import InstallationConfig, write_installation_config


def _client(tmp_path: Path, settings: Settings) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}")
    Base.metadata.create_all(engine)

    def _db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_the_page_says_where_the_files_are_and_how_much_room_they_take(tmp_path) -> None:
    (tmp_path / "recordings" / "r1").mkdir(parents=True)
    (tmp_path / "recordings" / "r1" / "audio.wav").write_bytes(b"x" * 2048)
    settings = Settings(data_dir=tmp_path, ollama_url="http://127.0.0.1:11434")

    body = _client(tmp_path, settings).get("/setup/privacy").text

    assert f"<code>{tmp_path}</code>" in body
    assert "Recordings" in body and "2 KB" in body
    assert "This machine" in body and "Stays on this machine" in body


def test_a_remote_default_server_shows_which_steps_leave(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path, providers={"cloud": ProviderConfig(url="https://llm.example.com")}
    )

    view = privacy_view(settings)
    meeting = next(w for w in view.workflows if w.name == "meeting-decisions")

    assert [step.where for step in meeting.steps] == ["in_app", "in_app", LEAVES, LEAVES]
    assert "Leaves this machine" in _client(tmp_path, settings).get("/setup/privacy").text


def test_with_a_local_server_nothing_leaves(tmp_path) -> None:
    view = privacy_view(Settings(data_dir=tmp_path, ollama_url="http://localhost:11434"))

    assert all(s.where in ("in_app", LOCAL_SERVER) for w in view.workflows for s in w.steps)


def test_the_retention_card_lives_here_now(tmp_path) -> None:
    write_installation_config(tmp_path, InstallationConfig(cores_per_chunk=1, parallel_chunks=1))
    client = _client(tmp_path, Settings(data_dir=tmp_path))

    assert 'id="vx-retention"' in client.get("/setup/privacy").text
    assert 'id="vx-retention"' not in client.get("/setup").text
    saved = client.post("/setup/retention", data={"retention_days": "30"}, follow_redirects=False)
    assert saved.headers["location"] == "/setup/privacy#vx-retention"
