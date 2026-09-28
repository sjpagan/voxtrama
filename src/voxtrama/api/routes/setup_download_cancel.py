"""POST /setup/local-processing/cancel-download: stop a queued or running
model download (the downloading panel's own "Cancel download").

api.routes.run_cancel's own shape, applied to a job with no Run behind it:
ask the queue to stop the job by id, tolerate it already being gone
(JobNotFound: the same "nothing left to wait on" case run_cancel.py
names), and publish "cancelled" so the next GET of step 2 stops polling
and shows the ordinary cards again.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import QueueDep, SettingsDep
from voxtrama.api.routes.setup_processing import PATH as LOCAL_PROCESSING_PATH
from voxtrama.queue.errors import JobNotFound, QueueUnavailable
from voxtrama.queue.job import JobId
from voxtrama.setup import publish_download_state, read_download_job_id

router = APIRouter()

CANCEL_PATH = f"{LOCAL_PROCESSING_PATH}/cancel-download"


@router.post(CANCEL_PATH)
def cancel_download(
    settings: SettingsDep,
    queue: QueueDep,
    hardware_profile: Annotated[str, Form()],
    cores_per_chunk: Annotated[int, Form()],
    parallel_chunks: Annotated[int, Form()],
) -> RedirectResponse:
    job_id = read_download_job_id(settings.data_dir)
    if job_id is not None:
        try:
            queue.cancel(JobId(job_id))
        except (JobNotFound, QueueUnavailable):
            pass
    publish_download_state(settings.data_dir, "cancelled")
    fields = {
        "hardware_profile": hardware_profile,
        "cores_per_chunk": cores_per_chunk,
        "parallel_chunks": parallel_chunks,
    }
    return RedirectResponse(f"{LOCAL_PROCESSING_PATH}?{urlencode(fields)}", 303)
