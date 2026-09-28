"""What a new-job upload may weigh, checked before the form is read.

POST /jobs read every part whole into memory (`upload.file.read()`), with
no limit anywhere: a multi-gigabyte video, dropped by mistake or sent by
another site, meant that much RAM in the web process, plus twice as much
on disk, and the process killed halfway. The declared length is checked
here before a byte of the body is parsed, against Settings.max_upload_mb
and against the room left in the data folder.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import Request, status

from voxtrama.api.errors import ProblemException

MB = 1024 * 1024

# The upload is written twice before the job owns it: the parts in a scratch
# folder, then the stored recording (and its 16 kHz copy) in the data folder.
ROOM_FACTOR = 3


def check_upload_size(request: Request, max_upload_mb: int, data_dir: Path) -> None:
    """Refuse a body with no length, one over the limit, or one the disk cannot hold."""
    declared = request.headers.get("content-length", "")
    if not declared.isdigit():
        raise ProblemException(
            status_code=status.HTTP_411_LENGTH_REQUIRED,
            code="length_required",
            title="The upload did not say how large it is",
            detail="Send the files from the new-job form.",
        )
    size = int(declared)
    if size > max_upload_mb * MB:
        raise ProblemException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            code="too_large",
            title="The upload is too large",
            detail=f"{size // MB} MB sent, {max_upload_mb} MB at most (VOXTRAMA_MAX_UPLOAD_MB).",
        )
    free, needed = shutil.disk_usage(data_dir).free, size * ROOM_FACTOR
    if needed > free:
        raise ProblemException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            code="insufficient_storage",
            title="Not enough room in the data folder",
            detail=f"This upload needs about {needed // MB} MB, {free // MB} MB is free.",
        )


def save_upload(source, destination: Path) -> None:
    """Copy an uploaded file to `destination` a megabyte at a time, never whole."""
    with destination.open("wb") as handle:
        shutil.copyfileobj(source, handle, MB)
