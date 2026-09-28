"""Migration 0021: the speaker_name table.

Same model as test_migration_people.py: a Recording, a Person and a run
already at revision 0020 (before speaker_name existed), then the
database upgrades to 0021 and a row can be written and read back,
unique on (recording_id, speaker_label) as db.speaker_naming relies on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

ALEMBIC_INI = "alembic.ini"


def _point_settings_at(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db_path}")
    from voxtrama.config.settings import get_settings

    get_settings.cache_clear()


def _insert_recording_and_person_at_0020(engine: Engine) -> None:
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
            text("INSERT INTO person (id, given_name, family_name) VALUES ('p1', 'Sarah', '')")
        )


def test_a_speaker_name_row_can_be_written_and_read_back_after_0021(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0020")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_recording_and_person_at_0020(engine)

    command.upgrade(config, "0021")

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO speaker_name (id, recording_id, speaker_label, person_id) "
                "VALUES ('sn1', 'rec1', 'spk0', 'p1')"
            )
        )

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT recording_id, speaker_label, person_id FROM speaker_name WHERE id = 'sn1'")
        ).one()
    assert (row.recording_id, row.speaker_label, row.person_id) == ("rec1", "spk0", "p1")


def test_the_same_label_twice_on_one_recording_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0020")

    engine = create_engine(f"sqlite:///{db_path}")
    _insert_recording_and_person_at_0020(engine)
    command.upgrade(config, "0021")

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO speaker_name (id, recording_id, speaker_label, person_id) "
                "VALUES ('sn1', 'rec1', 'spk0', 'p1')"
            )
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO speaker_name (id, recording_id, speaker_label, person_id) "
                    "VALUES ('sn2', 'rec1', 'spk0', 'p1')"
                )
            )


def test_downgrading_0021_drops_the_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "test.db"
    _point_settings_at(monkeypatch, db_path)
    config = Config(ALEMBIC_INI)
    command.upgrade(config, "0021")

    command.downgrade(config, "0020")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'")).all()
    assert "speaker_name" not in {row.name for row in tables}
