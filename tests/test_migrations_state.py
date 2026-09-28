"""Tests for voxtrama.db.migrations_state."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from voxtrama.config.settings import get_settings
from voxtrama.db.migrations_state import is_up_to_date

# Resolved relative to the current working directory, same as the module
# under test: tests run with the repository root as cwd.
ALEMBIC_INI = "alembic.ini"


def _point_settings_at(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    """Make migrations/env.py, via get_settings(), target a temp database."""
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()


def test_up_to_date_once_migrations_have_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    command.upgrade(Config(ALEMBIC_INI), "head")

    engine = create_engine(f"sqlite:///{db_path}")
    assert is_up_to_date(engine) is True


def test_not_up_to_date_on_a_database_without_migrations(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    assert is_up_to_date(engine) is False
