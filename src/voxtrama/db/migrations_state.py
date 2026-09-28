"""Whether the database's current revision matches Alembic's head.

One responsibility: compare two revision ids. It does not run migrations
and does not decide what to do when they differ: that is /health's job.
This module touches the database, so it is an adapter, not core.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

# Resolved the same way the `alembic` CLI resolves it: relative to the
# current working directory, which is /app in the image (see Dockerfile)
# and the repository root when tests run.
ALEMBIC_INI_PATH = Path("alembic.ini")


class MigrationsStateError(RuntimeError):
    """Raised when the current migration state cannot be determined."""


@dataclass(frozen=True)
class MigrationState:
    """Alembic's head revision, and the database's own current one.

    Kept apart, not collapsed into a bool, so a caller that needs to *say*
    the gap (api.routes.run_create's 503 detail, which must name what to
    do, not only that something is missing) has both ids to name without
    reading the database a second time.
    """

    current: str | None
    head: str | None

    @property
    def up_to_date(self) -> bool:
        return self.current == self.head


def read_migration_state(engine: Engine) -> MigrationState:
    """Read Alembic's head and the database's own current revision."""
    config = Config(str(ALEMBIC_INI_PATH))
    head_revision = ScriptDirectory.from_config(config).get_current_head()

    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_revision = context.get_current_revision()
    except SQLAlchemyError as exc:
        raise MigrationsStateError(str(exc)) from exc

    return MigrationState(current=current_revision, head=head_revision)


def is_up_to_date(engine: Engine) -> bool:
    """Return True if the database's current revision is Alembic's head."""
    return read_migration_state(engine).up_to_date
