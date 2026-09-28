"""Taking a job away for good, with what only it held.

The one place a whole run leaves: its steps, its row, its directory, and
the transcripts it produced. Used when a regenerated job replaces the old
one (housekeeping.replacement) and by the clean-up (housekeeping.prune).

A transcript is not always the removed run's alone: a run that reused its
transcription reads the same Transcript row, which still names the removed
run as its producer. So a transcript goes to an `heir` (the run that
reused it) when there is one without a transcript of its own, and is
deleted otherwise. The recording stays: another job may still use it,
and removing an unused one is housekeeping.prune's own decision.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, is_final
from voxtrama.db.models.run_redirect import RunRedirect
from voxtrama.db.models.speaker_name import SpeakerName
from voxtrama.db.models.step import RunStep
from voxtrama.db.models.transcript import Segment, Transcript


def contained(root: Path, name: str) -> Path | None:
    """`root/name`, or None when `name` would lead outside `root`."""
    candidate = (root / name).resolve()
    if candidate == root.resolve() or not candidate.is_relative_to(root.resolve()):
        return None
    return candidate


def delete_transcripts(session: Session, where: object) -> None:
    """Every Transcript matching `where`, with its segments."""
    ids = list(session.scalars(select(Transcript.id).where(where)))
    session.execute(delete(Segment).where(Segment.transcript_id.in_(ids)))
    session.execute(delete(Transcript).where(Transcript.id.in_(ids)))


def remove_recording_files(recordings_dir: Path, recording_id: str) -> None:
    """The recording's own folder on disk."""
    folder = contained(recordings_dir, recording_id)
    if folder is not None and folder.is_dir():
        shutil.rmtree(folder)


def remove_recording(session: Session, recordings_dir: Path, recording_id: str) -> None:
    """A recording no job uses any more: its transcripts, names, row and files."""
    delete_transcripts(session, Transcript.recording_id == recording_id)
    session.execute(delete(SpeakerName).where(SpeakerName.recording_id == recording_id))
    session.execute(delete(Recording).where(Recording.id == recording_id))
    session.commit()
    remove_recording_files(recordings_dir, recording_id)


def still_needed(session: Session, run_id: str) -> bool:
    """Whether a job not yet over was started from `run_id`, and may still read it."""
    users = session.scalars(select(Run.state).where(Run.reused_from_run_id == run_id))
    return any(not is_final(state) for state in users)


def heir_of(session: Session, run_id: str) -> str | None:
    """The latest job that reused one of `run_id`'s steps, if any."""
    reusing = select(RunStep.run_id).where(RunStep.reused_from_run_id == run_id)
    latest = select(Run.id).where(Run.id.in_(reusing)).order_by(Run.created_at.desc())
    return session.scalar(latest.limit(1))


def _has_transcript(session: Session, run_id: str) -> bool:
    found = select(Transcript.id).where(Transcript.produced_by_run_id == run_id).limit(1)
    return session.scalar(found) is not None


def _pass_on_transcripts(session: Session, run_id: str, heir: str | None) -> None:
    """The removed run's transcripts go to `heir`, else to the latest job
    that reused one of its steps (that job may read this very row),
    and are deleted only when neither can take them."""
    owned = Transcript.produced_by_run_id == run_id
    for candidate in (heir, heir_of(session, run_id)):
        if (
            candidate is not None
            and candidate != run_id
            and not _has_transcript(session, candidate)
        ):
            session.execute(update(Transcript).where(owned).values(produced_by_run_id=candidate))
            return
    delete_transcripts(session, owned)


def _redirect(session: Session, run_id: str, heir: str) -> None:
    """The removed address leads to `heir`, and so does every one that led to it."""
    moved = update(RunRedirect).where(RunRedirect.target_run_id == run_id)
    session.execute(moved.values(target_run_id=heir))
    session.merge(RunRedirect(run_id=run_id, target_run_id=heir))


def remove_run(session: Session, runs_dir: Path, run_id: str, heir: str | None = None) -> None:
    """Remove `run_id` for good. `heir` inherits its transcript and its address."""
    _pass_on_transcripts(session, run_id, heir)
    if heir is not None:
        _redirect(session, run_id, heir)
    else:
        session.execute(delete(RunRedirect).where(RunRedirect.target_run_id == run_id))
    session.execute(delete(RunStep).where(RunStep.run_id == run_id))
    session.execute(delete(Run).where(Run.id == run_id))
    session.commit()
    folder = contained(runs_dir, run_id)
    if folder is not None and folder.is_dir():
        shutil.rmtree(folder)
