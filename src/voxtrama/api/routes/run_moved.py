"""The job view of a job that was replaced leads to the job that replaced it.

A regenerated job that finished well takes the old one's
place, the old one is deleted, and its address leads to the new job, so a
bookmark or a link pasted somewhere keeps working. The pair is kept in
db.models.run_redirect. Only the view does this: the JSON resources keep
answering 404 for a run that no longer exists.

A redirect is raised rather than returned so the view keeps its one
lookup line. FastAPI answers an HTTPException with its own status and
headers, and a browser follows the Location of a 307.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.db.models.run import Run
from voxtrama.db.models.run_redirect import RunRedirect


def run_or_moved(run_id: str, session: Session) -> Run:
    """The run `run_id`; for one that was replaced, a redirect to its replacement."""
    redirect = session.get(RunRedirect, run_id)
    if redirect is not None and session.get(Run, run_id) is None:
        target = f"/runs/{redirect.target_run_id}/view"
        raise HTTPException(status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": target})
    return get_run_or_404(run_id, session)
