"""Readiness probe: reports whether the queue and migrations are ready.

/health is 200 only when the queue is reachable and the
database is at Alembic's head. It does not check models: their absence
is work the system will do, not an outage.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from voxtrama.api.deps import EngineDep, QueueDep
from voxtrama.db.migrations_state import MigrationsStateError, is_up_to_date
from voxtrama.queue.errors import QueueUnavailable

router = APIRouter()


@router.get("/health")
def health(queue: QueueDep, engine: EngineDep, response: Response) -> dict[str, str]:
    """Return 200 when the queue is reachable and migrations are applied."""
    try:
        queue.ping()
    except QueueUnavailable as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "reason": "queue", "detail": str(exc)}

    try:
        up_to_date = is_up_to_date(engine)
    except MigrationsStateError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "reason": "migrations", "detail": str(exc)}

    if not up_to_date:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unavailable",
            "reason": "migrations",
            "detail": "database is not at Alembic's head revision",
        }

    return {"status": "ok"}
