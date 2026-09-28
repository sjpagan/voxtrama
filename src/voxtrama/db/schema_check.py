"""Reads whether the database is as new as the code that queries it.

The verdict itself is `diagnostics.readiness_state.SchemaCheck`, with the
other three readiness states: this module only fills it in, because doing
so means opening a connection, and touching the database makes a module
an adapter. The upload gate that consumes the verdict is core
and must not reach in here.

`db.migrations_state.is_up_to_date` already answered this question
correctly the whole time, and `GET /health` was its only caller. So the
verdict existed and reached nobody while a run transcribed for eight
minutes and then died on `no such table: speaker_name`.

The reason says what to do, not only what is wrong. "database is not at
Alembic's head revision" is true and useless to whoever reads it: the fix
is rebuilding *every* service, because rebuilding only some leaves the
`migrate` image behind, which is how that failure happened.
"""

from __future__ import annotations

from sqlalchemy import Engine

from voxtrama.db.migrations_state import MigrationsStateError, is_up_to_date
from voxtrama.diagnostics.readiness_state import Readiness, SchemaCheck

SCHEMA_FIX = "run `docker compose build` for every service, then `docker compose up migrate`"


def check_schema(engine: Engine) -> SchemaCheck:
    """Check that the database's revision matches the one this code expects."""
    try:
        current = is_up_to_date(engine)
    except MigrationsStateError as exc:
        # UNKNOWN, never a plausible False: a revision that cannot be read
        # is not the same as one that is behind, and the two need different
        # words in front of a person (diagnostics.machine's own rule).
        # First line only: SQLAlchemy appends a link to its documentation
        # to its exception, and this sentence ends up in front of a person
        # in the gate panel. Measured by rendering the page, not
        # deduced.
        return SchemaCheck(
            state=Readiness.UNKNOWN,
            reason=f"the database revision could not be read: {str(exc).splitlines()[0]}",
        )
    if not current:
        return SchemaCheck(
            state=Readiness.NOT_READY,
            reason=f"the database is older than this version of Voxtrama: {SCHEMA_FIX}",
        )
    return SchemaCheck(state=Readiness.READY, reason="the database is at the expected revision")
