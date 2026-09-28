"""Migration 0023: the run_redirect table comes and goes."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_upgrading_to_0023_adds_run_redirect_and_downgrading_drops_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db_path}")
    from voxtrama.config.settings import get_settings

    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "0023")
    engine = create_engine(f"sqlite:///{db_path}")
    assert "run_redirect" in inspect(engine).get_table_names()

    command.downgrade(config, "0022")
    assert "run_redirect" not in inspect(create_engine(f"sqlite:///{db_path}")).get_table_names()
