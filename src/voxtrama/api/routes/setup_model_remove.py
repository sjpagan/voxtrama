"""POST /setup/local-processing/remove-model: drop a downloaded model's
cache from disk ("I can download and delete the library": the
library is managed independently of which profile is selected).

api.routes.setup_download_cancel's own shape, applied to disk instead of
a queued job: reject a forged or stale `hardware_profile` the same way the
POST download does, refuse to touch the disk while a download is under
way (removing files a running download might still be writing into would
leave the cache half there), and otherwise remove.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import SettingsDep
from voxtrama.api.routes.setup_processing import PATH as LOCAL_PROCESSING_PATH
from voxtrama.setup import IN_PROGRESS_STATES, read_download_state
from voxtrama.setup.profile_offers import PROFILE_KEYS
from voxtrama.transcription.asr import weights_for
from voxtrama.weights import remove_weights

router = APIRouter()

REMOVE_PATH = f"{LOCAL_PROCESSING_PATH}/remove-model"


@router.post(REMOVE_PATH)
def remove_model(
    settings: SettingsDep,
    hardware_profile: Annotated[str, Form()],
    cores_per_chunk: Annotated[int, Form()],
    parallel_chunks: Annotated[int, Form()],
) -> RedirectResponse:
    fields = {
        "hardware_profile": hardware_profile,
        "cores_per_chunk": cores_per_chunk,
        "parallel_chunks": parallel_chunks,
    }
    if hardware_profile not in PROFILE_KEYS:
        return RedirectResponse(
            f"{LOCAL_PROCESSING_PATH}?{urlencode({**fields, 'error': 'unavailable'})}", 303
        )
    state = read_download_state(settings.data_dir)
    if state is not None and state.state in IN_PROGRESS_STATES:
        return RedirectResponse(f"{LOCAL_PROCESSING_PATH}?{urlencode(fields)}", 303)
    remove_weights(weights_for(hardware_profile), settings.models_dir)
    return RedirectResponse(f"{LOCAL_PROCESSING_PATH}?{urlencode(fields)}", 303)
