"""What engine.reconcile needs to rewrite a Run's manifest without losing anything.

Split from reconcile.py, which owns deciding whether a Run is orphaned and
closing it, so neither file grows past the project's size limit. Everything
here only reads the database or the run's folder. Nothing here decides a
Run's fate.

The four functions below exist for the same reason: the
manifest already on disk was written by a process that had a live
ExecutionContext (a loaded workflow, a Recording, a Transcript, an
output.json it had just written). The reconciler has none of that.
Rewriting the manifest from empty context wherever one of these is missing
would leave a Run in `interrupted` with less information than it had a
moment before it closed, the mistake this module exists to avoid.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.models.transcript import Transcript
from voxtrama.engine.catalog import load_named_workflow
from voxtrama.manifest.output import output_path, read_run_output
from voxtrama.manifest.workflow_copy import read_workflow_copy
from voxtrama.manifest.writer import sha256_of_file
from voxtrama.workflow.definition import Workflow

logger = logging.getLogger(__name__)


def reloaded_workflow(runs_dir: Path, run_id: str, workflow_name: str) -> Workflow | None:
    """The definition `run_id` ran with, so the manifest keeps its hash.

    Prefers the run's own copy: the catalogue file named
    `workflow_name` can have changed since the run finished, but the copy
    is what `workflow.definition_sha256` was computed from. Only a run
    written before copies were kept has no copy on disk (those are not
    migrated backward). For one of those the catalogue is reread as this
    function always did, tolerant of a workflow that can no longer be
    loaded (renamed, removed, broken), and None only after trying, never
    without an attempt.
    """
    from_run = read_workflow_copy(runs_dir, run_id)
    if from_run is not None:
        return from_run
    try:
        return load_named_workflow(workflow_name)
    except Exception:
        logger.warning("could not reload workflow %r for an interrupted run", workflow_name)
        return None


def existing_output_digest(runs_dir: Path, run_id: str) -> str | None:
    """The sha256 of this run's output.json, if one was ever written.

    Not recomputed by calling write_run_output with nothing produced: the
    reconciler ran no step of this workflow, so it has nothing of its own
    to write, and doing so would overwrite what the steps that did run
    before the crash already produced.
    """
    path = output_path(runs_dir, run_id)
    if not path.is_file():
        return None
    return sha256_of_file(path)


def existing_produced(runs_dir: Path, run_id: str) -> dict[str, dict[str, Any]] | None:
    """What this run's steps produced, read back from output.json.

    The reconciler has no live ExecutionContext, so it cannot read
    `context.produced` the way engine.stepping does. This is the same
    dict, reread from the file a live run last wrote it to. None when no
    output.json was ever written (a run interrupted before any step
    produced anything), not `{}`: the difference is "nothing recorded yet"
    versus "recorded, and empty".
    """
    output = read_run_output(runs_dir, run_id)
    return None if output is None else output.steps


def recording_and_transcript(
    session: Session, run: Run
) -> tuple[Recording | None, Transcript | None]:
    """The Recording and Transcript a live run's context would have held.

    Read back from the database, the same Recording
    engine.context.build_context would resolve from `run.recording_id`, and
    the Transcript this run's transcribe step produced:
    `Transcript.produced_by_run_id == run.id`. Re-transcribing the same
    Recording under a later run must not make an earlier run's
    reconciliation pick up the newer row, since that Transcript's segments
    are not the ones the earlier run's evidence ever anchored to.

    Ordered by recency within that run, because two rows are legitimate:
    an extractive step may be retried, and
    engine.extractive_steps.run_transcribe writes a new Transcript on each
    attempt. The live context kept the last one it wrote, so that is the
    one to read back. Unordered, this would swap one silent guess for
    another.

    Only when no Transcript records this run (a row written before
    migration 0014 added that column) does this fall back to the most
    recently created Transcript of the Recording, the same guess this
    function used to make for every row. None only when `run` truly has
    none: no Recording at all, or interrupted before transcription ever
    produced one.
    """
    if run.recording_id is None:
        return None, None
    recording = session.scalar(select(Recording).where(Recording.id == run.recording_id))
    transcript = session.scalar(
        select(Transcript)
        .where(Transcript.produced_by_run_id == run.id)
        .order_by(Transcript.created_at.desc())
    )
    if transcript is None:
        transcript = session.scalar(
            select(Transcript)
            .where(Transcript.recording_id == run.recording_id)
            .order_by(Transcript.created_at.desc())
        )
    return recording, transcript
