"""The job form names a provider only when there is more than one."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db
from voxtrama.api.routes.job_choices import JobForm, job_choices
from voxtrama.config.providers import ProviderConfig
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base

TWO = {
    "box": ProviderConfig(url="http://127.0.0.1:11434"),
    "cloud": ProviderConfig(url="https://llm.example.com"),
}


def _client(tmp_path: Path, settings: Settings) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'shell.db'}")
    Base.metadata.create_all(engine)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_with_two_providers_the_form_offers_both_and_says_where_they_are(tmp_path) -> None:
    body = _client(tmp_path, Settings(data_dir=tmp_path, providers=TWO)).get("/").text

    assert '<select name="provider" data-default="box"' in body
    assert "box (local)" in body and "cloud (remote)" in body


def test_with_one_provider_there_is_nothing_to_choose(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, ollama_url="http://localhost:11434")

    assert 'name="provider"' not in _client(tmp_path, settings).get("/").text


def test_only_a_provider_other_than_the_default_is_the_job_s_own_choice(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, providers=TWO)

    assert job_choices(JobForm(provider="cloud"), settings).provider == "cloud"
    assert job_choices(JobForm(provider="box"), settings).provider is None
