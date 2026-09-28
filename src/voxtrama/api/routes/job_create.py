"""POST /jobs: the home's new-job form creates a job and opens it.

One submission carries everything the form shows: the audio (one file,
several consecutive parts joined, or tracks recorded together and mixed
into one recording, ingest.concat), the
workflow, the job's name and declared context, and the `Advanced`
fields. «Transcription only» picks the `transcribe-only` workflow, which
is what that option used to be.

Only a field moved off its default becomes a choice (api.routes.
job_defaults): the manifest's `choices` then says what this job decided,
and `environment` what it ran with. The Run is created by the same
engine.enqueue path every other entry point uses (run_start's own helper),
and the browser lands on the job's view with a 303, never a re-postable page.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from voxtrama.api.deps import DbDep, QueueDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.job_choices import JobForm, job_choices
from voxtrama.api.routes.recording_upload_errors import unsupported_media_problem
from voxtrama.api.routes.recording_upload_gate import require_ready
from voxtrama.api.routes.run_start import _enqueue_or_error
from voxtrama.api.routes.upload_limits import check_upload_size, save_upload
from voxtrama.api.routes.workflow_lookup import load_workflow_or_422
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.people import local_user
from voxtrama.ingest import UnsupportedMediaError, concatenate_parts, import_local_file

router = APIRouter()

TRANSCRIBE_ONLY = "transcribe-only"


def _safe_filename(name: str) -> str:
    """`name` without any directory part, so it cannot leave the folder it is written to."""
    candidate = Path(name).name
    return "upload" if candidate in ("", ".", "..") else candidate


def _refuse(title: str, detail: str) -> ProblemException:
    return ProblemException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_failed",
        title=title,
        detail=detail,
    )


def _import_audio(
    files: list[UploadFile], form: JobForm, label: str, session: Session, settings: Settings
) -> Recording:
    """Store the upload as one Recording: the file, the parts joined, or the tracks mixed."""
    merge = form.merge
    if len(files) > 1 and not merge:
        raise _refuse("Several files need joining", "Turn on «Merge into one recording».")
    created_by = local_user(session).id
    with tempfile.TemporaryDirectory(prefix="voxtrama-job-") as scratch:
        parts = []
        for index, upload in enumerate(files):
            # One folder per part: the name stays the one the person gave it.
            folder = Path(scratch) / f"{index:03d}"
            folder.mkdir()
            part = folder / _safe_filename(upload.filename or "part")
            save_upload(upload.file, part)  # never whole in memory
            parts.append(part)
        source = parts[0]
        try:
            if len(parts) > 1:
                source = Path(scratch) / f"{_safe_filename(label)}.flac"
                concatenate_parts(parts, source, together=form.parts_mode == "tracks")
            paths = get_paths(settings.data_dir)
            return import_local_file(session, source, paths, created_by=created_by)
        except UnsupportedMediaError as exc:
            raise unsupported_media_problem(exc) from exc


@router.post("/jobs", dependencies=[Depends(require_ready)])
async def create_job(
    request: Request, session: DbDep, settings: SettingsDep, queue: QueueDep
) -> RedirectResponse:
    """Import the audio, start the job with its choices, and open its view."""
    check_upload_size(request, settings.max_upload_mb, settings.data_dir)
    submitted = await request.form()
    form = JobForm.model_validate(
        {key: value for key, value in submitted.items() if isinstance(value, str)}
    )
    uploads = [item for item in submitted.getlist("files") if isinstance(item, UploadFile)]
    uploads = [upload for upload in uploads if upload.filename]
    if not uploads:
        raise _refuse("No audio was given", "Drop an audio file or choose one from disk.")
    label = form.label.strip() or Path(uploads[0].filename or "job").stem
    workflow_name = TRANSCRIBE_ONLY if form.transcribe_only else form.workflow_name
    workflow = load_workflow_or_422(workflow_name)
    choices = job_choices(form, settings)
    recording = _import_audio(uploads, form, label, session, settings)
    run = _enqueue_or_error(
        session, queue, workflow_name, workflow, recording.id, choices, local_user(session).id
    )
    run.label = label
    session.commit()
    return RedirectResponse(f"/runs/{run.id}/view", status_code=status.HTTP_303_SEE_OTHER)
