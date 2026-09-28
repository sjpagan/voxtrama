"""The rows that say where a run got to, written as it goes.

They exist so that progress and the run manifest read state rather than infer
it: progress shows which step is running, the manifest records what each one did, and
neither should have to parse logs to find out.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.workflow.definition import Step


def record_planned_steps(session: Session, run: Run, ordered: list[Step]) -> list[RunStep]:
    """Write one pending row per step before any of them runs.

    Up front, not as each step starts: a run killed halfway has to show the
    steps it never reached, or an interrupted run is indistinguishable from
    one that ended early on purpose.
    """
    rows = []
    for position, step in enumerate(ordered):
        row = RunStep(
            run_id=run.id,
            step_id=step.id,
            skill=step.skill,
            skill_version=step.skill_version,
            state=StepState.PENDING,
            position=position,
        )
        session.add(row)
        rows.append(row)
    # Committed, like every other transition here: a row that only exists
    # inside this transaction is invisible to anything reading the database
    # from another connection, which is every reader except the engine itself.
    session.commit()
    return rows


def mark_running(session: Session, row: RunStep) -> None:
    """Committed immediately: a step that never returns must already be visible.

    A flush would not do it. It makes the change visible inside this
    transaction and nowhere else, so a reader on another connection (the
    API, an interface, a person with a database client) sees the step as
    pending for as long as it runs, which is the stretch of time they are
    asking about.
    """
    row.state = StepState.RUNNING
    row.started_at = datetime.now(UTC)
    session.commit()


def record_provenance(
    session: Session,
    row: RunStep,
    *,
    model: str | None,
    model_revision: str | None,
    provider: str | None,
    host: str | None,
    profile_check_skipped: bool | None,
) -> None:
    """Write where `row`'s model ran, and commit it immediately.

    Called by the step that produces the provenance (engine.generative's
    run_generative, engine.extractive_steps' run_transcribe,
    engine.diarize_step's run_diarize) as soon as it is known, not by
    mark_succeeded/mark_failed below. A generative step can still fail
    *after* the model answered (a bad JSON body, output_schema_violation,
    a failed re-anchoring), and that failed run's manifest is
    the most important one there is. Committed immediately, like
    mark_running: the process that knows this can die (killed, OOM)
    before it reaches mark_succeeded or mark_failed, and
    engine.reconcile_manifest then rebuilds the manifest from what got
    committed. A flush would leave this invisible to that reconciliation,
    which is the one case this migration exists for.
    """
    row.model = model
    row.model_revision = model_revision
    row.provider = provider
    row.host = host
    row.profile_check_skipped = profile_check_skipped
    session.commit()


def write_step_hashes(session: Session, row: RunStep, *, input_sha256: str, reuse_key: str) -> None:
    """Write what `row` is about to consume, and commit it immediately.

    Called by engine.step_hashing.record_step_hashes, itself called from
    engine.preparation.execute_step right before it invokes the step's
    implementation. Every dependency has produced by then, and this step
    has not. Committed immediately, like record_provenance above: the
    process can die mid-step, and engine.reconcile_manifest must still say
    which inputs a step was tried against, not only whether it succeeded.
    A step that later fails keeps these values because they describe the
    attempt, not its outcome. A retry overwrites them with the identical
    result, since the inputs do not change between attempts.
    """
    row.input_sha256 = input_sha256
    row.reuse_key = reuse_key
    session.commit()


def mark_succeeded(session: Session, row: RunStep) -> None:
    """Committed for the same reason as mark_running: a finished step is a fact."""
    row.state = StepState.SUCCEEDED
    row.finished_at = datetime.now(UTC)
    session.commit()


def mark_failed(row: RunStep, exc: Exception) -> None:
    row.state = StepState.FAILED
    row.error = str(exc)
    row.finished_at = datetime.now(UTC)


def mark_skipped(session: Session, row: RunStep) -> None:
    """A step whose condition was false, or that depended on one that was.

    Committed like every other transition here, and left without
    started_at/finished_at: a step that never ran has nothing to report
    for either, and setting them would say it did.
    """
    row.state = StepState.SKIPPED
    session.commit()
