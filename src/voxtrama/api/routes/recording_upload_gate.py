"""Refuses an import when the installation cannot yet carry it.

"A gate that lives only in the page is not a gate". The
home page closes its upload box when a readiness check is not green, and
that alone stops nobody: `curl -F` reaches the same route with the box
never rendered, and so does a stale tab left open while the machine
changed underneath it.

503 rather than 422: nothing is wrong with the request, the installation
is not ready to serve it: the same code and the same reasoning `/health`
already uses for the identical facts. Whoever reads it should try again
after fixing the state, which is what 503 means and 422 does not.

The detail names every missing state and repeats the reason each check
gave, because "not ready" without which one is a message that sends
someone looking in four places.

A FastAPI dependency rather than a call inside each route: the routes
that import a recording are not the place to decide whether the machine
can, and a test about importing a file can then declare the installation
ready through dependency_overrides instead of monkey-patching four
readiness probes it has no opinion about.
"""

from __future__ import annotations

from fastapi import status

from voxtrama.api.deps import EngineDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.db.schema_check import check_schema
from voxtrama.diagnostics.readiness import read_readiness
from voxtrama.rendering.upload_gate import upload_gate


def require_ready(settings: SettingsDep, engine: EngineDep) -> None:
    """Raise 503 naming every state that is not ready, or return and let the import run."""
    gate = upload_gate(read_readiness(settings), check_schema(engine))
    if gate.allowed:
        return
    raise ProblemException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="not_ready",
        title="This installation cannot take a recording yet",
        detail="; ".join(f"{blocker.key}: {blocker.reason}" for blocker in gate.blockers),
    )
