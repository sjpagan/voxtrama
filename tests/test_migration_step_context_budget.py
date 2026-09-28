"""Migration 0019: context budget on run_step.

Same model as test_migration_step_model_provenance.py: a run_step is
written at revision 0018 (before these three columns existed), then the
database upgrades to 0019. That proves a step already recorded before
these columns existed keeps its row, with the new columns reading NULL rather than
an invented value.
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


def _insert_run_step_at_0018(engine: Engine) -> None:
    """Write one run and one run_step, in the shape they had at 0018."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO run (id, workflow_name, workflow_version, state, created_at) "
                "VALUES ('run1', 'demo', '1.0.0', 'succeeded', :created_at)"
            ),
            {"created_at": datetime(2026, 1, 1, tzinfo=UTC)},
        )
        conn.execute(
            text(
                "INSERT INTO run_step "
                "(id, run_id, step_id, skill, skill_version, state, position, attempts) "
                "VALUES ('step1', 'run1', 'summarize', 'summarize', '1.0.0', "
                "'succeeded', 0, 1)"
            )
        )


def _context_budget_columns(engine: Engine) -> tuple[object, object, object]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT context_window_tokens, context_window_at_risk, output_resumptions "
                "FROM run_step WHERE id = 'step1'"
            )
        ).one()
    return row.context_window_tokens, row.context_window_at_risk, row.output_resumptions


def test_a_run_step_written_at_0018_survives_upgrading_to_0019_with_null_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0018")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run_step_at_0018(engine)

    command.upgrade(config, "0019")

    assert _context_budget_columns(engine) == (None, None, None)


def test_downgrading_and_upgrading_again_keeps_the_step_and_its_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0018")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run_step_at_0018(engine)

    command.upgrade(config, "0019")
    command.downgrade(config, "0018")
    command.upgrade(config, "0019")

    assert _context_budget_columns(engine) == (None, None, None)
    with engine.connect() as conn:
        skill = conn.execute(text("SELECT skill FROM run_step WHERE id = 'step1'")).scalar()
    assert skill == "summarize"
