"""Seed the one local User a real, migrated database always has.

Fixtures across the test suite build their own schema with
Base.metadata.create_all instead of running migrations (a file-backed
engine, since some of them are read from another thread, as in the
`client` fixtures that use this). Migration 0011 seeds exactly one User.
This does the same, so db.people.local_user(), now called by the CLI
and the API routes it exercises, finds one instead of raising.
"""

from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from voxtrama.db.models.user import ROLE_OWNER, User


def seed_local_user(engine: Engine) -> None:
    """Insert the single `owner` User a migrated database always has."""
    with Session(engine) as session:
        session.add(User(given_name="Owner", family_name="", role=ROLE_OWNER))
        session.commit()


def stamp_head(engine: Engine) -> None:
    """Mark `engine` as migrated to Alembic's head, without running a migration.

    Base.metadata.create_all already gives these fixtures the current
    schema (by definition the same one Alembic's head describes) but
    writes no `alembic_version` row, which db.migrations_state.is_up_to_date
    now reads before api.routes.run_create accepts a Run. Written by hand
    rather than through `alembic stamp`, which would have to be pointed at
    this exact file-backed engine through Settings.database_url first, a
    second thing to keep in sync with the one already passed in.
    """
    head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": head}
        )
