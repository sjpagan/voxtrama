"""Which Transcript a job shows: the one it made, or the one it reused.

`Transcript.produced_by_run_id` names the job whose transcribe step wrote
the row. A job that reused its transcription (Regenerate, Retry) wrote
no row of its own: its transcribe output only carries the `transcript_id`
it adopted (engine.reuse_adopt). Looking only at `produced_by_run_id`,
a regenerated job would read "No transcript yet" while its recap quoted
that very transcript. The owner is often another job on
the same recording that is still there, so housekeeping.removal never
moved the row over.

The job's own row comes first, then the `transcript_id` its output.json
records, the same generic rule engine.reuse_adopt follows: any step
output that carries one, no skill name looked up.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.transcript import Transcript
from voxtrama.manifest.output import RunOutput


def adopted_transcript_id(output: RunOutput | None) -> str | None:
    """The first `transcript_id` a step of `output` carries, or None."""
    if output is None:
        return None
    for step_output in output.steps.values():
        transcript_id = step_output.get("transcript_id")
        if isinstance(transcript_id, str) and transcript_id:
            return transcript_id
    return None


def transcript_for(session: Session, run_id: str, output: RunOutput | None) -> Transcript | None:
    """The Transcript `run_id` made, else the one its output says it reused."""
    own = session.scalar(
        select(Transcript)
        .where(Transcript.produced_by_run_id == run_id)
        .order_by(Transcript.created_at.desc())
    )
    if own is not None:
        return own
    transcript_id = adopted_transcript_id(output)
    return session.get(Transcript, transcript_id) if transcript_id else None
