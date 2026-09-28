"""Migration 0011: person and user tables, and created_by on run/recording.

Same model as test_migration_run_choices.py: a run and a recording are
written at revision 0010 (before Person and User existed), then the
database upgrades to 0011. That proves upgrading an installation that
predates them neither loses those rows nor invents an author for them.
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


def _insert_run_and_recording_at_0010(engine: Engine) -> None:
    """Write one Recording and one Run, in the shape they had at 0010."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO recording "
                "(id, original_filename, stored_path, content_sha256, duration_seconds, "
                "media_format, imported_at) "
                "VALUES (:id, :original_filename, :stored_path, :content_sha256, "
                ":duration_seconds, :media_format, :imported_at)"
            ),
            {
                "id": "rec1",
                "original_filename": "clip.wav",
                "stored_path": "recordings/rec1/clip.wav",
                "content_sha256": "0" * 64,
                "duration_seconds": 12.0,
                "media_format": "wav",
                "imported_at": datetime(2026, 1, 1, tzinfo=UTC),
            },
        )
        conn.execute(
            text(
                "INSERT INTO run "
                "(id, workflow_name, workflow_version, recording_id, state, created_at) "
                "VALUES (:id, :workflow_name, :workflow_version, :recording_id, "
                ":state, :created_at)"
            ),
            {
                "id": "r1",
                "workflow_name": "demo",
                "workflow_version": "1.0.0",
                "recording_id": "rec1",
                "state": "succeeded",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
            },
        )


def test_a_run_and_recording_written_at_0010_survive_upgrading_to_0011(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0010")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_run_and_recording_at_0010(engine)

    command.upgrade(config, "0011")

    with engine.connect() as conn:
        run_row = conn.execute(text("SELECT created_by FROM run WHERE id = 'r1'")).one()
        recording_row = conn.execute(
            text("SELECT created_by FROM recording WHERE id = 'rec1'")
        ).one()
        owners = conn.execute(text("SELECT role FROM user")).all()

    assert run_row.created_by is None
    assert recording_row.created_by is None
    assert [row.role for row in owners] == ["owner"]


def test_downgrading_and_upgrading_again_leaves_exactly_one_local_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The user 0011 seeds must not double up on a downgrade/upgrade cycle.

    A CE installation never downgrades in practice, but the migration
    must still tell the truth about what it does: dropping the `user`
    table on downgrade and reseeding it on the next upgrade is honest
    (there is no user data to lose below 0011) as long as it lands back
    at exactly one row, not two.
    """
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0011")

    command.downgrade(config, "0010")
    command.upgrade(config, "0011")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        user_count = conn.execute(text("SELECT COUNT(*) FROM user")).scalar()
    assert user_count == 1
