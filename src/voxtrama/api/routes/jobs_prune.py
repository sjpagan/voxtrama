"""POST /jobs/prune: the clean-up, now, from the Jobs page.

The clean-up runs by itself (worker.prune_schedule) and
the Jobs page also has a button for it, with the same one-week rule
(housekeeping.prune). The page comes back saying how much went.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.housekeeping.prune import prune

router = APIRouter()


@router.post("/jobs/prune")
def prune_route(session: DbDep, settings: SettingsDep) -> RedirectResponse:
    """Clean up, then back to the Jobs page with the count."""
    report = prune(session, settings.data_dir, retention_days=settings.retention_days)
    return RedirectResponse(f"/jobs?cleaned={report.total}", status_code=status.HTTP_303_SEE_OTHER)
