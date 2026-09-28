"""Migration 0016: reused_from_run_id on run and run_step.

Same model as test_migration_step_input_hashes.py: a run and its run_step
are written at revision 0015 (before either column existed), then the
database upgrades to 0016. That proves a run and a step already recorded
before these columns existed keep their rows, with the new columns reading NULL
rather than an invented value.
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


def _insert_run(engine: Engine, run_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO run (id, workflow_name, workflow_version, state, created_at) "
                "VALUES (:id, 'demo', '1.0.0', 'succeeded', :created_at)"
            ),
            {"id": run_id, "created_at": datetime(2026, 1, 1, tzinfo=UTC)},
        )


def _insert_run_step_at_0015(engine: Engine) -> None:
    """Write one run and one run_step, in the shape they had at 0015: no reuse columns."""
    _insert_run(engine, "run1")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO run_step "
                "(id, run_id, step_id, skill, skill_version, state, position, attempts) "
                "VALUES ('step1', 'run1', 'summarize', 'summarize', '1.0.0', "
                "'succeeded', 0, 1)"
            )
        )


def _reused_columns(engine: Engine) -> tuple[object, object]:
    with engine.connect() as conn:
        run_value = conn.execute(
            text("SELECT reused_from_run_id FROM run WHERE id = 'run1'")
        ).scalar()
        step_value = conn.execute(
            text("SELECT reused_from_run_id FROM run_step WHERE id = 'step1'")
        ).scalar()
    return run_value, step_value


def test_a_run_and_step_written_at_0015_survive_upgrading_to_0016_with_null_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0015")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run_step_at_0015(engine)

    command.upgrade(config, "0016")

    assert _reused_columns(engine) == (None, None)


def test_both_columns_accept_a_real_run_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The FK each column carries resolves to a real run, not just a same-shaped string."""
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run(engine, "source")
    _insert_run(engine, "run1")
    with engine.begin() as conn:
        conn.execute(text("UPDATE run SET reused_from_run_id = 'source' WHERE id = 'run1'"))
        conn.execute(
            text(
                "INSERT INTO run_step "
                "(id, run_id, step_id, skill, skill_version, state, position, attempts, "
                "reused_from_run_id) "
                "VALUES ('step1', 'run1', 'summarize', 'summarize', '1.0.0', "
                "'succeeded', 0, 1, 'source')"
            )
        )

    assert _reused_columns(engine) == ("source", "source")


def test_downgrading_and_upgrading_again_keeps_the_step_and_its_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same round trip 0015's own test asks of its two columns, now for these two."""
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0015")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run_step_at_0015(engine)

    command.upgrade(config, "0016")
    command.downgrade(config, "0015")
    command.upgrade(config, "0016")

    assert _reused_columns(engine) == (None, None)
    with engine.connect() as conn:
        skill = conn.execute(text("SELECT skill FROM run_step WHERE id = 'step1'")).scalar()
    assert skill == "summarize"
