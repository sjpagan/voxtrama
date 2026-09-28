"""Migration 0015: input_sha256 and reuse_key on run_step.

Same model as test_migration_step_model_provenance.py: a run_step is
written at revision 0014 (before these two columns existed), then the
database upgrades to 0015. That proves a step already recorded before this
issue keeps its row, with the new columns reading NULL rather than an
invented value.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

ALEMBIC_INI = "alembic.ini"


def _point_settings_at(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db_path}")
    from voxtrama.config.settings import get_settings

    get_settings.cache_clear()


def _insert_run(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO run (id, workflow_name, workflow_version, state, created_at) "
                "VALUES ('run1', 'demo', '1.0.0', 'succeeded', :created_at)"
            ),
            {"created_at": datetime(2026, 1, 1, tzinfo=UTC)},
        )


def _insert_run_step_at_0014(engine: Engine) -> None:
    """Write one run_step, in the shape it had at 0014: no input hash columns."""
    _insert_run(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO run_step "
                "(id, run_id, step_id, skill, skill_version, state, position, attempts) "
                "VALUES ('step1', 'run1', 'summarize', 'summarize', '1.0.0', "
                "'succeeded', 0, 1)"
            )
        )


def _hash_columns(engine: Engine) -> tuple[object, object]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT input_sha256, reuse_key FROM run_step WHERE id = 'step1'")
        ).one()
    return row.input_sha256, row.reuse_key


def test_a_run_step_written_at_0014_survives_upgrading_to_0015_with_null_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0014")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run_step_at_0014(engine)

    command.upgrade(config, "0015")

    assert _hash_columns(engine) == (None, None)


def test_downgrading_and_upgrading_again_keeps_the_step_and_its_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same round trip 0013's own test asks of its five columns, now for
    these two: a downgrade that drops them, followed by an upgrade that
    adds them back, must leave the row's other data intact and the new
    columns NULL again.
    """
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0014")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run_step_at_0014(engine)

    command.upgrade(config, "0015")
    command.downgrade(config, "0014")
    command.upgrade(config, "0015")

    assert _hash_columns(engine) == (None, None)
    with engine.connect() as conn:
        skill = conn.execute(text("SELECT skill FROM run_step WHERE id = 'step1'")).scalar()
    assert skill == "summarize"
