"""POST /models/download: enqueue one library key's own weights.

api.routes.setup_processing's own POST, applied to any of LIBRARY_KEYS
instead of only a hardware profile: publish "queued" on the same
DOWNLOAD_SLOT the wizard's own step 2 uses, then hand the job to the same
queue.submit_download. One download at a time for the whole
installation, so a key already covered by one in progress is a
no-op rather than a second job racing it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import QueueDep, SettingsDep
from voxtrama.api.routes.models import DOWNLOAD_PATH, LIBRARY_KEYS, PATH, weight_set_for
from voxtrama.setup import (
    IN_PROGRESS_STATES,
    publish_download_state,
    read_download_state,
    write_download_job_id,
)

router = APIRouter()


@router.post(DOWNLOAD_PATH)
def download_weight_set(
    settings: SettingsDep, queue: QueueDep, key: Annotated[str, Form()]
) -> RedirectResponse:
    if key not in LIBRARY_KEYS:
        return RedirectResponse(PATH, 303)
    state = read_download_state(settings.data_dir)
    if state is not None and state.state in IN_PROGRESS_STATES:
        return RedirectResponse(PATH, 303)
    weights = weight_set_for(key)
    publish_download_state(settings.data_dir, "queued", model_label=weights.label)
    job_id = queue.submit_download(key)
    write_download_job_id(settings.data_dir, str(job_id))
    return RedirectResponse(PATH, 303)
