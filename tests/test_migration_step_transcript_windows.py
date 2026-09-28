"""Migration 0024: run_step.transcript_windows comes and goes."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _columns(db_path: Path) -> set[str]:
    return {
        c["name"] for c in inspect(create_engine(f"sqlite:///{db_path}")).get_columns("run_step")
    }


def test_0024_adds_transcript_windows_and_downgrading_drops_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db_path}")
    from voxtrama.config.settings import get_settings

    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "0024")
    assert "transcript_windows" in _columns(db_path)

    command.downgrade(config, "0023")
    assert "transcript_windows" not in _columns(db_path)
