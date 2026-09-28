"""What a Recording already has, for api.routes.workflow_choose's own header
and cards: whether it has been transcribed, whether any prior Run
exists at all, and which workflow already has a succeeded result.

Split out of workflow_choose.py to keep that route's own file under the
project's file-length limit. These three queries share nothing with the panel it
renders beyond the recording_id they all take, and none of them belongs in
rendering (a presenter does not query).
"""

from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Transcript


def has_prior_run(session: Session, recording_id: str) -> bool:
    """Whether `recording_id` already has at least one Run: the same
    presence check api.routes.shell's own pending-Recording query already
    makes in reverse (`~exists()`), reused here to tell "Re-run with a
    different workflow" apart from a first choice (workflow_choose.py's
    own docstring).
    """
    return bool(session.scalar(select(exists().where(Run.recording_id == recording_id))))


def transcribed(session: Session, recording_id: str) -> dict[str, int | None]:
    """`{recording_id: speaker_estimate}` when a Transcript exists for it, `{}` when
    none does yet (see rendering.recordings' own docstring on why that distinction, not
    duration alone, is what the header needs)."""
    transcript = session.scalar(
        select(Transcript)
        .where(Transcript.recording_id == recording_id)
        .order_by(Transcript.created_at.desc())
    )
    if transcript is None:
        return {}
    return {recording_id: transcript.speaker_estimate}


def already_run(session: Session, recording_id: str) -> dict[str, str]:
    """`{workflow_name: run_id}` of the most recent succeeded Run of each workflow
    already run on `recording_id`, so a workflow that already has a
    result offers "View result" instead of asking to run it again blind."""
    runs = session.scalars(
        select(Run)
        .where(Run.recording_id == recording_id, Run.state == RunState.SUCCEEDED)
        .order_by(Run.created_at.desc())
    )
    found: dict[str, str] = {}
    for run in runs:
        found.setdefault(run.workflow_name, run.id)
    return found
