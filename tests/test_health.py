"""Tests for the /health readiness endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fakes.queue import InMemoryQueue
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from voxtrama.api.app import create_app
from voxtrama.api.deps import get_engine, get_queue
from voxtrama.config.settings import get_settings

ALEMBIC_INI = "alembic.ini"


def _engine_at_head(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> object:
    """Build an engine for a temp database migrated to Alembic's head."""
    db_path = tmp_path / "head.db"
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    command.upgrade(Config(ALEMBIC_INI), "head")
    return create_engine(f"sqlite:///{db_path}")


def test_health_ok_when_queue_reachable_and_migrations_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app()
    app.dependency_overrides[get_queue] = InMemoryQueue
    app.dependency_overrides[get_engine] = lambda: _engine_at_head(tmp_path, monkeypatch)
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_503_when_queue_unreachable() -> None:
    unavailable_queue = InMemoryQueue()
    unavailable_queue.available = False
    app = create_app()
    app.dependency_overrides[get_queue] = lambda: unavailable_queue
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["reason"] == "queue"
    assert "detail" in body


def test_health_503_when_migrations_not_applied(tmp_path: Path) -> None:
    app = create_app()
    app.dependency_overrides[get_queue] = InMemoryQueue
    app.dependency_overrides[get_engine] = lambda: create_engine(
        f"sqlite:///{tmp_path / 'behind.db'}"
    )
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["reason"] == "migrations"
    assert "detail" in body
