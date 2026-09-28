"""Migration 0013: model provenance on run_step.

Same model as test_migration_recording_source.py: a run_step is written at
revision 0012 (before these five columns existed), then the database
upgrades to 0013. That proves a step already recorded before these
columns existed keeps its row, with the new columns reading NULL rather
than an invented value.
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


def _insert_run_step_at_0012(engine: Engine) -> None:
    """Write one run_step, in the shape it had at 0012: no provenance columns."""
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


def _provenance_columns(engine: Engine) -> tuple[object, object, object, object, object]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT model, model_revision, provider, host, profile_check_skipped "
                "FROM run_step WHERE id = 'step1'"
            )
        ).one()
    return row.model, row.model_revision, row.provider, row.host, row.profile_check_skipped


def test_a_run_step_written_at_0012_survives_upgrading_to_0013_with_null_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0012")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run_step_at_0012(engine)

    command.upgrade(config, "0013")

    assert _provenance_columns(engine) == (None, None, None, None, None)


def test_downgrading_and_upgrading_again_keeps_the_step_and_its_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same round trip 0012's own test asks of source_title/source_url,
    now for these five: a downgrade that drops them, followed by an
    upgrade that adds them back, must leave the row's other data intact
    and the new columns NULL again.
    """
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0012")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run_step_at_0012(engine)

    command.upgrade(config, "0013")
    command.downgrade(config, "0012")
    command.upgrade(config, "0013")

    assert _provenance_columns(engine) == (None, None, None, None, None)
    with engine.connect() as conn:
        skill = conn.execute(text("SELECT skill FROM run_step WHERE id = 'step1'")).scalar()
    assert skill == "summarize"
