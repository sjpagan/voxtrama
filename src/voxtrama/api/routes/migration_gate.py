"""503 before a Run exists if the database is behind Alembic's head.

Split out of run_create.py, already at the project's line limit before this
gate existed. Measured on real audio: a run that starts anyway can
transcribe for minutes before dying on a table a later migration would
have created, and the queue had already accepted the work by then. Not a
`rule_rejected` (its own 422): the caller chose nothing wrong, the
installation is what fell behind, and GET /health already answers that
with 503 (voxtrama.api.routes.health). This is the same fact, checked
here before enqueueing rather than as a standing probe. worker.tasks does
the same check again for a Run already queued when the schema fell
behind. The two do not share this function because ProblemException, the
shape one of them raises, is an API concern the worker has no use for.
"""

from __future__ import annotations

from fastapi import status
from sqlalchemy import Engine

from voxtrama.api.errors import ProblemException
from voxtrama.db.migrations_state import MigrationsStateError, read_migration_state


def reject_unless_schema_current(engine: Engine) -> None:
    """Raise a 503 ProblemException unless the database is at Alembic's head.

    The detail names what to run, not only what is missing: whoever reads
    it has no reason to already know that a schema behind head is fixed by
    `docker compose build` (no arguments) followed by `docker compose up
    migrate`.
    """
    try:
        state = read_migration_state(engine)
    except MigrationsStateError as exc:
        raise ProblemException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="migrations_pending",
            title="The database schema could not be read",
            detail=str(exc),
        ) from exc
    if state.up_to_date:
        return
    raise ProblemException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="migrations_pending",
        title="The database schema is behind Alembic's head",
        detail=(
            f"Database is at revision {state.current!r}, Alembic's head is {state.head!r}. "
            "Run `docker compose build` (no arguments) then `docker compose up migrate` "
            "before starting a run."
        ),
    )
