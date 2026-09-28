"""GET /recordings/{id}/peaks: the numbers the player draws its waveform from.

A separate route from `/audio` because it answers a different question:
that one streams the recording, this one describes its shape. The browser
used to derive the shape from the stream itself (182 MB downloaded and
232 MB of decoded PCM for a 21-minute file, measured), which is why
`run_waveform.js` refused to draw anything past a duration ceiling. The
same shape is 6 KB here.

The peaks are computed on the first request and cached beside the audio
(ingest.peaks), so the second caller pays nothing. The API does not
import from voxtrama.engine: the path comes from the data
directory and Recording.stored_path, as recording_audio.py resolves it.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models.recording import Recording
from voxtrama.ingest.errors import UnsupportedMediaError
from voxtrama.ingest.peaks import load_or_compute

router = APIRouter()


class PeaksOut(BaseModel):
    """One level per bucket, each 0.0 to 1.0, plus the duration they span."""

    duration_seconds: float
    peaks: list[float]


def _recording_or_404(recording_id: str, session: Session) -> Recording:
    recording = session.get(Recording, recording_id)
    if recording is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="The recording does not exist",
            detail=f"No recording with id {recording_id}",
        )
    return recording


def _audio_path(recording: Recording, settings: Settings) -> Path:
    path = get_paths(settings.data_dir).data_dir / recording.stored_path
    if not path.exists():
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="The recording's audio file is missing",
            detail=f"No file at {path}",
        )
    return path


@router.get("/recordings/{recording_id}/peaks", response_model=PeaksOut)
def get_recording_peaks(recording_id: str, session: DbDep, settings: SettingsDep) -> PeaksOut:
    """Return the waveform levels of a Recording, computing them once.

    A file ffmpeg cannot decode answers 422 rather than 500: the recording
    exists and the request was well formed, but the media cannot
    produce a waveform, and the player is expected to carry on without
    one rather than treat it as an outage.
    """
    recording = _recording_or_404(recording_id, session)
    audio_path = _audio_path(recording, settings)
    try:
        peaks = load_or_compute(audio_path, recording.duration_seconds)
    except UnsupportedMediaError as exc:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="unsupported_media",
            title="No waveform can be drawn for this recording",
            detail=str(exc),
        ) from exc
    return PeaksOut(duration_seconds=recording.duration_seconds, peaks=peaks)
