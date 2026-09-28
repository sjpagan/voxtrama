"""POST /models/remove: drop one library key's own cache from disk.

api.routes.setup_model_remove's own shape, applied to any of LIBRARY_KEYS
instead of only a hardware profile: reject an unknown key or one already
covered by a download in flight, otherwise remove, which is allowed even for
the profile the installation is actively using, or for ECAPA-TDNN (the
next run simply downloads it again, an announced wait rather than a guard
that would only look like protection).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import SettingsDep
from voxtrama.api.routes.models import LIBRARY_KEYS, PATH, REMOVE_PATH, weight_set_for
from voxtrama.setup import IN_PROGRESS_STATES, read_download_state
from voxtrama.weights import remove_weights

router = APIRouter()


@router.post(REMOVE_PATH)
def remove_weight_set(settings: SettingsDep, key: Annotated[str, Form()]) -> RedirectResponse:
    if key not in LIBRARY_KEYS:
        return RedirectResponse(PATH, 303)
    state = read_download_state(settings.data_dir)
    if state is not None and state.state in IN_PROGRESS_STATES:
        return RedirectResponse(PATH, 303)
    remove_weights(weight_set_for(key), settings.models_dir)
    return RedirectResponse(PATH, 303)
