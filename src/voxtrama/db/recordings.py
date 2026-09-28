"""Query layer for Recording: correcting its source after the fact.

Adapter, not core (db.people's own docstring classifies this package the
same way): correcting a title someone got wrong is an entrypoint concern,
and this is the one door it goes through, the same role db.people.py plays
for User.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording


class RecordingNotFoundError(RuntimeError):
    """Raised when `correct_source` is given an id no Recording has."""


def correct_source(
    session: Session,
    recording_id: str,
    *,
    source_title: str | None = None,
    source_url: str | None = None,
) -> Recording:
    """Update `source_title` and/or `source_url` on an already-imported Recording.

    Only the ones given: `None` here means "leave unchanged", not "clear
    the field": the two columns already use `None` to mean "no provenance
    to report" (migration 0012), so a correction that overwrote both every
    time would force calling it twice just to fix one.

    Does not touch any manifest already written to disk, and nothing here
    could: a manifest is a snapshot `writer.py` produced once, while a run
    was executing, not a view this function could refresh. The manifest
    records "how a run was executed", meant to be copied and attached.
    Two copies of the one file must never read differently, so this
    correction reaches runs from here on, never ones already closed.
    """
    recording = session.get(Recording, recording_id)
    if recording is None:
        raise RecordingNotFoundError(f"no recording with id {recording_id!r}")
    if source_title is not None:
        recording.source_title = source_title
    if source_url is not None:
        recording.source_url = source_url
    session.commit()
    return recording
