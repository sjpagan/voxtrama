"""GET /recordings/{id}/audio: serve the audio file with Range support.

Split out of recordings.py because creating a Recording and streaming its
bytes are two different subjects. The module name says which one this is.
Range-header parsing lives in range_header.py: a separate subject again.

The API does not import from voxtrama.engine: the path is derived
from the data directory and Recording.stored_path here, the same way
engine.context.audio_path_for does it for the run pipeline, but independently.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.range_header import (
    RangeUnsatisfiable,
    range_not_satisfiable,
    resolve_range,
)
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models.recording import Recording

router = APIRouter()

_CHUNK_SIZE = 64 * 1024


def _audio_path_for(recording: Recording, settings: Settings) -> Path:
    """Where on disk the audio of `recording` lives.

    stored_path is relative to the data directory, so a backup
    restored on a machine where that directory sits elsewhere still resolves.
    """
    return get_paths(settings.data_dir).data_dir / recording.stored_path


def _response_headers(start: int, end: int, file_size: int, is_partial: bool) -> dict[str, str]:
    """Build the headers that describe what slice of the file is being sent."""
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1)}
    if is_partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    return headers


# For security, the type comes from what ffprobe found, never from
# the uploaded name. A WAV named `x.html` was served as text/html, and the
# script inside it ran as the app.
_MEDIA_TYPES = {
    "wav": "audio/wav", "w64": "audio/wav", "rf64": "audio/wav", "mp3": "audio/mpeg",
    "flac": "audio/flac", "ogg": "audio/ogg", "mov": "audio/mp4", "mp4": "audio/mp4",
    "m4a": "audio/mp4", "matroska": "audio/webm", "webm": "audio/webm",
    "aac": "audio/aac", "aiff": "audio/aiff",
}  # fmt: skip

# Whatever the bytes are, nothing in them runs, and the type above is final.
AUDIO_HEADERS = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"}


def _media_type_for(recording: Recording) -> str:
    """The audio's own media type, so the browser need not sniff it."""
    return _MEDIA_TYPES.get(recording.media_format or "", "application/octet-stream")


def _iter_file(path: Path, start: int, end: int) -> Iterator[bytes]:
    """Yield the bytes from `start` to `end` inclusive, in fixed-size chunks.

    A generator for StreamingResponse, so neither the requested range nor
    the whole file ever sits in memory at once: audio can run to hundreds
    of MB, and the `low` hardware profile targets small machines.
    """
    remaining = end - start + 1
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _get_recording_or_404(recording_id: str, session: Session) -> Recording:
    """Look up a Recording by id, or raise the 404 the route must return."""
    recording = session.get(Recording, recording_id)
    if recording is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="The recording does not exist",
            detail=f"No recording with id {recording_id}",
        )
    return recording


def _existing_audio_path(recording: Recording, settings: Settings) -> Path:
    """Resolve where the audio lives, or raise the declared error if it is gone."""
    audio_path = _audio_path_for(recording, settings)
    if not audio_path.exists():
        raise ProblemException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal",
            title="The recording's audio file is missing",
            detail=f"No file at {audio_path}",
        )
    return audio_path


@router.get("/recordings/{recording_id}/audio")
def get_recording_audio(
    recording_id: str, request: Request, session: DbDep, settings: SettingsDep
) -> StreamingResponse:
    """Stream a Recording's audio file, honouring a single-range `Range` header."""
    recording = _get_recording_or_404(recording_id, session)
    audio_path = _existing_audio_path(recording, settings)
    file_size = audio_path.stat().st_size

    try:
        start, end, is_partial = resolve_range(request.headers.get("range"), file_size)
    except RangeUnsatisfiable as exc:
        raise range_not_satisfiable(file_size) from exc

    response_status = status.HTTP_206_PARTIAL_CONTENT if is_partial else status.HTTP_200_OK
    return StreamingResponse(
        _iter_file(audio_path, start, end),
        status_code=response_status,
        headers={**_response_headers(start, end, file_size, is_partial), **AUDIO_HEADERS},
        media_type=_media_type_for(recording),
    )
