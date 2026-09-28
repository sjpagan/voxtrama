"""The loop that runs a workflow's steps in order, and catches an engine fault while one runs.

Split from engine.stepping, which owns the per-step building blocks this
loop calls (whether to skip a step, how to announce it, the manifest).
Kept apart so stepping.py stays under the project's size limit once this loop
also had to name which step it was on when the engine itself (not the
step) went wrong.
"""

from __future__ import annotations

from voxtrama.db.models.step import RunStep
from voxtrama.engine.fallback import fallback_ids, skip_unused_fallbacks
from voxtrama.engine.progress import mark_skipped
from voxtrama.engine.retry import StepExecutor, run_with_fallback
from voxtrama.engine.stepping import (
    StepFailure,
    SteppingTarget,
    announce,
    blocked_by_condition,
    publish_manifest,
)
from voxtrama.workflow.definition import Step


def run_steps(
    target: SteppingTarget, ordered: list[Step], execute: StepExecutor
) -> StepFailure | None:
    """Execute the steps in order, publishing where the run has got to.

    Returns the failure that stopped it, or None. A step whose retries and
    fallback (if any) are both exhausted stops the run: carrying on would
    mean diarising a transcript that does not exist and producing a result
    that is formally valid and empty. That is how a product that sells
    verifiability loses the trust of whoever uses it.
    """
    step_by_id = {step.id: step for step in ordered}
    row_by_id = {row.step_id: row for row in target.rows}
    ids_used_as_fallback = fallback_ids(ordered)
    # Condition-skipped steps only, not failed ones: an unhandled failure
    # stops the run outright (the loop breaks below), so there is nothing
    # left to propagate a skip to. A failure a fallback recovered is not a
    # skip either: the run deliberately continues past it.
    skipped: set[str] = set()

    failure: StepFailure | None = None
    for position, (step, row) in enumerate(zip(ordered, target.rows, strict=True)):
        if step.id in ids_used_as_fallback:
            # Only runs when invoked below, as another step's recovery.
            continue
        failure = _run_one_step(
            target, step, row, position, len(ordered), skipped, row_by_id, step_by_id, execute
        )
        if failure is not None:
            break

    skip_unused_fallbacks(target.context.session, ids_used_as_fallback, row_by_id)
    return failure


def _run_one_step(
    target: SteppingTarget,
    step: Step,
    row: RunStep,
    position: int,
    total: int,
    skipped: set[str],
    row_by_id: dict[str, RunStep],
    step_by_id: dict[str, Step],
    execute: StepExecutor,
) -> StepFailure | None:
    """Run `step`'s turn in the loop, naming it if the engine itself faults.

    A step's own failure already comes back as a value from run_with_fallback
    (see StepFailure's docstring). This catches everything else that can go
    wrong while `step` is being handled (a condition that fails to evaluate,
    a manifest write that fails to publish), which would otherwise look
    like an engine fault with no step to blame.
    """
    try:
        if blocked_by_condition(step, skipped, target.context):
            skipped.add(step.id)
            mark_skipped(target.context.session, row)
            publish_manifest(target)
            return None

        announce(target, total, position, step)
        outcome = run_with_fallback(
            target.runs_dir,
            target.run,
            target.context,
            step,
            row,
            step_by_id,
            row_by_id,
            execute,
            target.skills,
        )
        publish_manifest(target)
        if outcome is not None:
            return StepFailure(*outcome)
        return None
    except Exception as exc:  # noqa: BLE001 - engine fault while handling `step`, not the step's own
        # Not BaseException: KeyboardInterrupt/SystemExit mean someone asked
        # the run to stop, not that the work went wrong. Reporting either as
        # a failed run would hide that the stop was requested, not caused.
        return StepFailure(exc, step.id)
