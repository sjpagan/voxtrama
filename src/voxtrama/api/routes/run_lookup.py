"""Resolve a run_id against the database, the one way every route does it.

The same relationship workflow_lookup.py has to POST /runs and GET
/workflows/{name}/choices: runs.py's GET /runs/{id} and the GET
/runs/{id}/events both need this exact lookup, and each writing its own copy
is how two routes quietly disagree about what "the run does not exist"
means. That had happened here before, when runs.py and
run_cancel.py each carried an identical, independently-written
`_get_run_or_404`.
"""

from __future__ import annotations

from fastapi import status
from sqlalchemy.orm import Session

from voxtrama.api.errors import ProblemException
from voxtrama.db.models.run import Run


def get_run_or_404(run_id: str, session: Session) -> Run:
    """Return the Run row for `run_id`, or raise the 404 problem for a missing resource."""
    run = session.get(Run, run_id)
    if run is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="The run does not exist",
            detail=f"No run with id {run_id}",
        )
    return run
