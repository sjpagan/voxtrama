"""Resolve a recording_id against the database, for the two routes
that both need it: GET .../choose-workflow and POST .../runs share one
Recording, and each writing its own copy is the exact failure run_lookup.py
and workflow_lookup.py already name: two routes quietly disagreeing about
what "the recording does not exist" means.

This module does not close that gap for the codebase as a whole: it was
written for these two new call sites only. run_create.py and
recording_audio.py each still carry their own, independently-written copy
of the same lookup, so as of this module the same 404 is written three
times, not two, one of them here. Consolidating all three into this one
is a change still owed that this commit does not make. A reader landing
on either of those two files should not assume it already happened.
"""

from __future__ import annotations

from fastapi import status
from sqlalchemy.orm import Session

from voxtrama.api.errors import ProblemException
from voxtrama.db.models.recording import Recording


def get_recording_or_404(recording_id: str, session: Session) -> Recording:
    """Return the Recording row for `recording_id`, or the 404 for a missing one."""
    recording = session.get(Recording, recording_id)
    if recording is None:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="The recording does not exist",
            detail=f"No recording with id {recording_id}",
        )
    return recording
