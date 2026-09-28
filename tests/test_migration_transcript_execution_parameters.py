"""Migration 0020: cpu_threads and num_workers on transcript.

Same model as test_migration_transcript_provenance.py: a transcript is
written at revision 0019 (before these two columns existed), then the
database upgrades to 0020. That proves a transcript already recorded
before these columns existed keeps its row, with the new columns reading NULL rather
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


def _insert_recording(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO recording "
                "(id, original_filename, stored_path, content_sha256, duration_seconds, "
                "media_format, imported_at) "
                "VALUES ('rec1', 'clip.wav', 'recordings/rec1/clip.wav', :sha, 12.0, "
                "'wav', :imported_at)"
            ),
            {"sha": "0" * 64, "imported_at": datetime(2026, 1, 1, tzinfo=UTC)},
        )


def _insert_transcript_at_0019(engine: Engine) -> None:
    """Write one transcript, in the shape it had at 0019: no execution-parameter columns."""
    _insert_recording(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO transcript "
                "(id, recording_id, language, model_name, model_revision, hardware_profile, "
                "created_at) "
                "VALUES ('t1', 'rec1', 'en', 'whisper-test', 'rev-1', 'cpu', :created_at)"
            ),
            {"created_at": datetime(2026, 1, 1, tzinfo=UTC)},
        )


def _execution_parameter_columns(engine: Engine) -> tuple[object, object]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT cpu_threads, num_workers FROM transcript WHERE id = 't1'")
        ).one()
    return row.cpu_threads, row.num_workers


def test_a_transcript_written_at_0019_survives_upgrading_to_0020_with_null_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0019")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_transcript_at_0019(engine)

    command.upgrade(config, "0020")

    assert _execution_parameter_columns(engine) == (None, None)


def test_downgrading_and_upgrading_again_keeps_the_transcript_and_its_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0019")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_transcript_at_0019(engine)

    command.upgrade(config, "0020")
    command.downgrade(config, "0019")
    command.upgrade(config, "0020")

    assert _execution_parameter_columns(engine) == (None, None)
    with engine.connect() as conn:
        model_name = conn.execute(
            text("SELECT model_name FROM transcript WHERE id = 't1'")
        ).scalar()
    assert model_name == "whisper-test"
