"""Migration 0012: source_title and source_url on recording.

Same model as test_migration_people.py: a recording is written at revision
0011 (before these two columns existed), then the database upgrades to
0012. That proves an installation from before these columns keeps its
recordings, with the new columns reading NULL rather than an invented empty
string.
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


def _insert_recording_at_0011(engine: Engine) -> None:
    """Write one Recording, in the shape it had at 0011: no source columns."""
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


def _source_columns(engine: Engine) -> tuple[object, object]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT source_title, source_url FROM recording WHERE id = 'rec1'")
        ).one()
    return row.source_title, row.source_url


def test_a_recording_written_at_0011_survives_upgrading_to_0012_with_null_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0011")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_recording_at_0011(engine)

    command.upgrade(config, "0012")

    assert _source_columns(engine) == (None, None)


def test_downgrading_and_upgrading_again_keeps_the_recording_and_its_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The round trip 0011 asks of `user` must hold for these two columns too:
    a downgrade that drops them, followed by an upgrade that adds them back,
    must leave the row's other data intact and the new columns NULL again.
    """
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0011")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_recording_at_0011(engine)

    command.upgrade(config, "0012")
    command.downgrade(config, "0011")
    command.upgrade(config, "0012")

    assert _source_columns(engine) == (None, None)
    with engine.connect() as conn:
        original_filename = conn.execute(
            text("SELECT original_filename FROM recording WHERE id = 'rec1'")
        ).scalar()
    assert original_filename == "clip.wav"
