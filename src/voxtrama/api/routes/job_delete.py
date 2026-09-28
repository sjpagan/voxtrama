"""POST /jobs/{id}/delete: delete only the parts of a job that were ticked.

`Delete...` opens a dialog with three boxes (Audio,
Transcript, Recap), and only what is ticked goes. What is left unchecked
stays. Ticking all three removes the job itself.

- Recap: the run's output.json, the text a workflow extracted.
- Transcript: the Transcript this job produced, with its segments.
- Audio: the recording's files on disk. When another job still uses the
  same recording (a regenerated job), this job lets go
  of it instead: it loses its player, the other job keeps the audio, and
  the files go with the last job that uses them. Each job behaves as if the
  audio were its own.
- All three: the job row, its steps and its directory (api.routes.
  run_delete), its transcripts, and the recording itself when no other job
  uses it. A shared recording stays for the other job, never a refusal.

Refused (409) only while a job regenerated from this one is still running:
it may be reading this job's steps.

A job still going is stopped from its own view first (409), the same rule
DELETE /runs/{id} keeps. The browser goes back to /jobs with a 303.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_delete import _reject_unless_final, _run_directory
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models.run import Run
from voxtrama.db.models.transcript import Transcript
from voxtrama.housekeeping.removal import (
    delete_transcripts,
    remove_recording,
    remove_recording_files,
    remove_run,
    still_needed,
)

router = APIRouter()


def _shared(session: Session, run: Run) -> bool:
    """Whether another job uses the same recording."""
    others = select(func.count()).where(Run.recording_id == run.recording_id, Run.id != run.id)
    return bool(run.recording_id) and session.scalar(others) > 0


def _remove_recap(settings: Settings, run_id: str) -> None:
    folder = _run_directory(get_paths(settings.data_dir).runs_dir, run_id)
    if folder is not None:
        Path(folder / "output.json").unlink(missing_ok=True)


def _delete_whole_job(session: Session, settings: Settings, run: Run) -> None:
    recording_id, shared = run.recording_id, _shared(session, run)
    paths = get_paths(settings.data_dir)
    remove_run(session, paths.runs_dir, run.id)
    if recording_id and not shared:
        remove_recording(session, paths.recordings_dir, recording_id)


def _let_go_of_audio(session: Session, settings: Settings, run: Run) -> None:
    """This job's audio goes: the files, or only this job's hold on shared ones."""
    if _shared(session, run):
        run.recording_id = None  # the other job keeps the recording and its files
        session.commit()
    else:
        remove_recording_files(get_paths(settings.data_dir).recordings_dir, run.recording_id)


@router.post("/jobs/{run_id}/delete")
def delete_job_parts(
    run_id: str,
    session: DbDep,
    settings: SettingsDep,
    audio: Annotated[bool, Form()] = False,
    transcript: Annotated[bool, Form()] = False,
    recap: Annotated[bool, Form()] = False,
) -> RedirectResponse:
    """Delete what was ticked. All three removes the job itself."""
    run = get_run_or_404(run_id, session)
    _reject_unless_final(run)
    if still_needed(session, run.id):
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            title="A job regenerated from this one is still running",
            detail="Wait for it to finish: it may be reading this job's steps.",
        )
    if audio and transcript and recap:
        _delete_whole_job(session, settings, run)
    else:
        if recap:
            _remove_recap(settings, run.id)
        if transcript:
            delete_transcripts(session, Transcript.produced_by_run_id == run.id)
            session.commit()
        if audio and run.recording_id:
            _let_go_of_audio(session, settings, run)
    return RedirectResponse("/jobs", status_code=status.HTTP_303_SEE_OTHER)
