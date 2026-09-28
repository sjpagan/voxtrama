"""POST /setup/skip: go to the new-job form with the machine's proposal.

The guided setup opens on a first visit (setup.wizard_start). This is the
way past it for someone who wants to start a job first and tune later:
nothing is decided here, the proposal stays in force, and the setup stays
one click away under Settings.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import SettingsDep
from voxtrama.setup.wizard_start import skip_setup

router = APIRouter()


@router.post("/setup/skip")
def skip(settings: SettingsDep) -> RedirectResponse:
    """Leave the marker and go home; an unwritable data folder still goes home."""
    try:
        skip_setup(settings.data_dir)
    except OSError:
        pass  # Settings > Data & privacy says why the folder cannot be written
    return RedirectResponse("/", status_code=303)
