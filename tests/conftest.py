"""Shared pytest fixtures: an in-memory database session and queue."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fakes.events_client import build_app
from fakes.queue import InMemoryQueue
from fastapi import FastAPI
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.models import Base, User
from voxtrama.db.models.user import ROLE_OWNER


@pytest.fixture(autouse=True)
def _queue_url_env(monkeypatch: pytest.MonkeyPatch, tmp_path_factory) -> Iterator[None]:
    """Point every test at a queue URL and a data directory that exist.

    The data directory matters: commands refuse to work
    against one that is missing or unwritable, naming the variable rather
    than failing deeper with an OSError. Without this, every CLI test
    would be testing that check instead of what it means to test.
    """
    monkeypatch.setenv("VOXTRAMA_QUEUE_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path_factory.mktemp("data")))
    # TestClient's own Host, next to the defaults api.security allows.
    monkeypatch.setenv("VOXTRAMA_ALLOWED_HOSTS", '["127.0.0.1", "localhost", "::1", "testserver"]')
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """An isolated in-memory SQLite session with the schema already created.

    Seeded with the one User migration 0011 creates: the
    CLI and the API routes now resolve it via db.people.local_user()
    before creating a Run or Recording, so a session without one would
    not match what a database that ran its migrations looks like.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(given_name="Owner", family_name="", role=ROLE_OWNER))
        session.commit()
        yield session


@pytest.fixture
def queue() -> InMemoryQueue:
    """A fresh in-memory Queue double."""
    return InMemoryQueue()


@pytest.fixture
def events_app(tmp_path: Path) -> tuple[FastAPI, Engine, Path]:
    """A real app, its database engine and its runs_dir, for GET /runs/{id}/events tests."""
    return build_app(tmp_path)


@pytest.fixture
def eval_dir() -> Path:
    """The private evaluation set, or skip: it is never part of the repository.

    Recordings of real people live outside the repository by design: what
    is committed under an open licence cannot be taken back.
    """
    raw = os.environ.get("VOXTRAMA_EVAL_DIR")
    if not raw:
        pytest.skip("VOXTRAMA_EVAL_DIR is not set: the evaluation set is not available here")
    path = Path(raw).expanduser()
    if not (path / "reference.csv").is_file():
        pytest.skip(f"{path} has no reference.csv")
    return path


@pytest.fixture(autouse=True)
def _setup_already_done(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Most tests open the home page on a data folder with no voxtrama.toml.

    Such a first visit is sent to the guided setup
    (setup.wizard_start). Tests about the new-job form are not about that
    redirect, so it is off unless a test is marked `first_visit`.
    """
    if "first_visit" not in request.keywords:
        monkeypatch.setattr("voxtrama.api.routes.shell.setup_pending", lambda data_dir: False)
