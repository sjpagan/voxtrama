"""Which of a run's steps a later derivation has already superseded.

The original table of step states names `stale` for "a step upstream was
regenerated" and calls it blocking. A later refinement narrows that: in
this additive model no artefact is ever destroyed (`run_transcribe`
always `session.add`s a new `Transcript`, never updates one), so nothing
computed here is ever orphaned evidence. What exists is
weaker and non-blocking: a step has been **`superseded`** by a more recent
derivation of the same recording. The cascade is computed, not written:
nothing here reads a manifest or a file, only rows already committed by
engine.step_hashing and engine.progress.

Two rules combine.

**Direct.** Step P of run R is superseded by step Q when Q belongs to a
later run (`Run.created_at`) of the same recording, Q succeeded, and
`Q.input_sha256 == P.input_sha256` while `Q.reuse_key != P.reuse_key`:
the same point in the chain, but different work done on it. Two steps
sharing a `reuse_key` are the same work, or a reuse, and
never supersede each other.

**Cascade.** `depends_on` read backwards: a step superseded by the direct
rule drags down every step of its run that depends on it, transitively.
`diarize` never matches the direct rule against a re-transcription (its
`input_sha256` differs, since it depends on a different transcript), but
it inherits the supersession from the `transcribe` step it depends on
within the same run.

The cascade needs the run's dependency graph. `_reloaded_workflow` reads
it back from the run's `workflow.json`, falling back to
the catalogue file named by `run.workflow_name` only for a run predating
that copy, with the same tolerance
engine.reconcile_manifest.reloaded_workflow shows for an interrupted run.
A workflow renamed or removed leaves the cascade unavailable for that
run, never an error. The direct rule above still holds without it.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.catalog import load_named_workflow
from voxtrama.manifest.workflow_copy import read_workflow_copy
from voxtrama.workflow.definition import Workflow

logger = logging.getLogger(__name__)


def _reloaded_workflow(runs_dir: Path, run_id: str, workflow_name: str) -> Workflow | None:
    """The run's workflow copy, or the catalogue for a run without one.

    A run's `depends_on` graph must be the one it ran with, not whatever
    the catalogue says today (see this module's docstring). Falls back to
    `load_named_workflow` only for a run written before runs kept their
    own workflow copy, tolerant as it always was of a workflow no longer
    there to load.
    """
    from_run = read_workflow_copy(runs_dir, run_id)
    if from_run is not None:
        return from_run
    try:
        return load_named_workflow(workflow_name)
    except Exception:
        logger.warning("could not reload workflow %r to compute its cascade", workflow_name)
        return None


def _direct_supersessor(session: Session, run: Run, step: RunStep) -> str | None:
    """The most recent later run whose step supersedes `step` by the direct rule.

    None when `step` never consumed anything (`input_sha256` unset, as for
    a step the engine skipped for its condition) or when nothing later
    matches. Ordered newest-first: several later runs can each qualify,
    and the most recent one is the current answer to "what superseded
    this", not the first run that once did.
    """
    if step.input_sha256 is None:
        return None
    return session.scalar(
        select(Run.id)
        .join(RunStep, RunStep.run_id == Run.id)
        .where(Run.recording_id == run.recording_id)
        .where(Run.created_at > run.created_at)
        .where(RunStep.state == StepState.SUCCEEDED)
        .where(RunStep.input_sha256 == step.input_sha256)
        .where(RunStep.reuse_key != step.reuse_key)
        .order_by(Run.created_at.desc())
    )


def _dependency_map(workflow: Workflow | None, step_ids: set[str]) -> dict[str, list[str]]:
    """step_id -> its depends_on, restricted to steps this run has a row for."""
    if workflow is None:
        return {}
    return {
        step.id: [dep for dep in step.depends_on if dep in step_ids]
        for step in workflow.steps
        if step.id in step_ids
    }


def superseded_steps(
    session: Session, run: Run, runs_dir: Path, workflow: Workflow | None = None
) -> dict[str, str]:
    """step_id -> the run_id that supersedes it, for every step of `run` that is.

    A step absent from the returned dict is not superseded. `workflow`
    lets a caller that already holds the run's definition (a live
    ExecutionContext, a test) skip reloading it. Left as None (the API's
    case), `_reloaded_workflow` reads it via `runs_dir` and `run.id`.

    When two of a step's dependencies were superseded by two different
    runs, the first one `depends_on` declares wins. It is arbitrary only in
    a case that barely exists (a step whose upstream was rebuilt twice
    over, by two separate runs), and every candidate is equally true: the
    step is superseded either way, and which run to name is the only
    question. Declaration order at least gives the same answer on every
    call.

    Steps are walked in `RunStep.position` order, the topological order
    engine.steps.resolve_order produced when the run was planned. By the
    time a step is reached here every step it `depends_on` has already
    been decided, so one pass is enough for the cascade, with no separate
    graph traversal.
    """
    if run.recording_id is None:
        return {}
    if workflow is None:
        workflow = _reloaded_workflow(runs_dir, run.id, run.workflow_name)
    steps = session.scalars(
        select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.position)
    ).all()
    deps = _dependency_map(workflow, {row.step_id for row in steps})

    result: dict[str, str] = {}
    for row in steps:
        by = _direct_supersessor(session, run, row)
        if by is None:
            by = next((result[dep] for dep in deps.get(row.step_id, []) if dep in result), None)
        if by is not None:
            result[row.step_id] = by
    return result
