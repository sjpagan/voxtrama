"""Migration 0010: a Run written at 0009 reads `choices` as NULL, not `{}`.

No server_default on the new column (see the migration's own comment): a
database that already has Runs from before this column must be able to tell "chose
nothing" apart from "chose an empty set of choices" the moment it upgrades.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

ALEMBIC_INI = "alembic.ini"


def _point_settings_at(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db_path}")
    from voxtrama.config.settings import get_settings

    get_settings.cache_clear()


def test_a_run_written_at_0009_has_null_choices_after_upgrading_to_0010(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0009")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO run (id, workflow_name, workflow_version, state, created_at) "
                "VALUES (:id, :workflow_name, :workflow_version, :state, :created_at)"
            ),
            {
                "id": "r1",
                "workflow_name": "demo",
                "workflow_version": "1.0.0",
                "state": "pending",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            },
        )

    command.upgrade(config, "0010")

    with engine.connect() as conn:
        choices = conn.execute(text("SELECT choices FROM run WHERE id = 'r1'")).scalar()
    assert choices is None
