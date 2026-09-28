"""POST /recordings: import a local audio file as a Recording.

The path is on the machine Voxtrama runs on (the same thing the CLI
accepts), not an upload: browser file input and URL ingest are separate.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.people import local_user
from voxtrama.ingest import UnsupportedMediaError, import_local_file

router = APIRouter()


class RecordingIn(BaseModel):
    """The local filesystem path of the audio file to import."""

    path: Path


class RecordingOut(BaseModel):
    """The public representation of a Recording."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    stored_path: str
    content_sha256: str
    duration_seconds: float
    media_format: str
    imported_at: datetime


def _resolve_within_data_dir(path: Path, settings: Settings) -> Path:
    """Resolve `path` and reject it if it falls outside the data directory.

    The allowed-root rule covers writes (a server-side path is a primitive
    the caller controls with the process's own permissions), and the same
    reasoning holds for a read: nothing here is served to an authenticated
    user, so an unrestricted path would let any request reach any file
    voxtrama can read, not just the caller's own audio. `VOXTRAMA_EXTRA_ROOTS`
    is not implemented yet, so the data directory is the only allowed root.

    Resolving (not comparing strings) is what that rule asks for: it
    follows symlinks, so a link inside the data directory that points
    outside it is caught the same way a bare `..` would be.

    `rule_rejected`, not `validation_failed`: the body matches its
    schema (a syntactically valid path to a file that may well exist), and
    it is the allowed root that refuses it. Not a 403 either: the
    `local` profile has no identity, so there is nothing the
    caller could authenticate as to make this path allowed.
    """
    allowed_root = settings.data_dir.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed_root):
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="rule_rejected",
            title="The path is outside the allowed root",
            detail=f"{path} does not resolve under the data directory ({allowed_root})",
        )
    return resolved


@router.post("/recordings", status_code=status.HTTP_201_CREATED, response_model=RecordingOut)
def create_recording(body: RecordingIn, session: DbDep, settings: SettingsDep) -> RecordingOut:
    """Import the audio file at `body.path` and return the Recording it becomes."""
    resolved_path = _resolve_within_data_dir(body.path, settings)

    if not resolved_path.exists():
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="The audio file does not exist",
            detail=f"No file at {resolved_path}",
        )

    paths = get_paths(settings.data_dir)
    created_by = local_user(session).id
    try:
        return import_local_file(session, resolved_path, paths, created_by=created_by)
    except UnsupportedMediaError as exc:
        raise ProblemException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code="unsupported_media",
            title="The file is not a supported audio format",
            detail=str(exc),
        ) from exc
