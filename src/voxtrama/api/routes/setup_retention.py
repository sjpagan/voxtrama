"""POST /setup/retention: how long a finished job's data stays.

An installation deletes nothing until someone
sets a limit here. «Never» takes it off again. The limit is the
installation's level of workflow.retention: a workflow or a job can only
shorten it. It is applied when the application starts and from the Jobs
page's clean-up (housekeeping.retention), not the moment it is saved.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import SettingsDep
from voxtrama.setup import write_installation_config
from voxtrama.setup.installation import read_installation_config

router = APIRouter()

CHOICES = (7, 30, 90, 365)


@router.post("/setup/retention")
def save_retention(
    settings: SettingsDep, retention_days: Annotated[str, Form()] = ""
) -> RedirectResponse:
    """Write the limit ("" is none); a value the page does not offer is ignored."""
    config = read_installation_config(settings.data_dir)
    days = int(retention_days) if retention_days.isdigit() else None
    if config is not None and (days in CHOICES or not retention_days):
        write_installation_config(
            settings.data_dir, config.model_copy(update={"retention_days": days})
        )
    return RedirectResponse("/setup/privacy#vx-retention", status_code=303)
