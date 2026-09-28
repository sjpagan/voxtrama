"""Builds and persists the Recording row import_local_file writes.

Split out of local_file.py only to keep that file's probe/copy machinery
and this row's now-larger shape (two extra columns) each under the
project's 150-line limit. This module has no logic of its own worth reading
next to ffprobe and the chunked copy, only the row's fields.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording


def persist_new_recording(
    session: Session,
    recording_id: str,
    original_filename: str,
    stored_path: str,
    copy_result: tuple[str, float, str],
    created_by: str | None,
    source_title: str | None,
    source_url: str | None,
) -> Recording:
    """Build the Recording row for a completed copy, persist it, and return it.

    Called only once the copy import_local_file made is known to have
    succeeded (that function's docstring says why the row is never
    written earlier). `copy_result` is `(content_sha256,
    duration_seconds, media_format)`, what probing and hashing the file
    found, bundled into one argument rather than three.

    `source_title` and `source_url` came from the URL import,
    since removed: rows written before keep them, new ones leave them
    None.
    """
    content_sha256, duration_seconds, media_format = copy_result
    recording = Recording(
        id=recording_id,
        original_filename=original_filename,
        stored_path=stored_path,
        content_sha256=content_sha256,
        duration_seconds=duration_seconds,
        media_format=media_format,
        imported_at=datetime.now(UTC),
        created_by=created_by,
        source_title=source_title,
        source_url=source_url,
    )
    session.add(recording)
    session.commit()
    return recording
