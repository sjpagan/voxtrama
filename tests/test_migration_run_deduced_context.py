"""Migration 0025: run.deduced_context comes and goes."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _columns(db_path: Path) -> set[str]:
    return {c["name"] for c in inspect(create_engine(f"sqlite:///{db_path}")).get_columns("run")}


def test_0025_adds_deduced_context_and_downgrading_drops_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db_path}")
    from voxtrama.config.settings import get_settings

    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "0025")
    assert "deduced_context" in _columns(db_path)

    command.downgrade(config, "0024")
    assert "deduced_context" not in _columns(db_path)
