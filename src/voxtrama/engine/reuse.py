"""Deciding whether a step's output can be reused from a source run.

engine.preparation.execute_step calls reuse_if_available right after
record_step_hashes has given `row` its reuse_key, and runs the step itself
only when the answer is False.

Split out of preparation.py instead of folded into step_hashing.py:
step_hashing computes what a step *would need* to be reused, while this
module is the one place that reads another run's rows and disk output.
Adopting an output once found is engine.reuse_adopt, split again for the
same reason.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.reuse_adopt import apply_reused_output
from voxtrama.engine.validation import resolve_skill, validate_output
from voxtrama.manifest.output import read_run_output
from voxtrama.workflow.definition import Step
from voxtrama.workflow.loader import SkillRegistry


def find_reusable_output(
    session: Session, source_run_id: str | None, reuse_key: str
) -> tuple[RunStep, dict[str, Any]] | None:
    """The succeeded RunStep of `source_run_id` whose reuse_key matches, and its output.

    None when there is no source run to ask (a run that did not pass
    `--reuse-from`), when nothing in it matches, or when a match exists but
    its output is no longer on disk (the reuse tests need the second
    case: a source run of a *different* recording never matches, since its
    reuse_keys carry a different recording_sha256). All of these give
    engine.preparation.execute_step the same answer (recompute, which is
    always valid), so they are not told apart here.

    Ordered by position. Two matches are legitimate: two steps of the source
    run declaring the same skill over the same inputs hash identically by
    design, so without an order this would return whichever row the
    database handed back first. The earliest is the one whose output the
    rest of that run was built on.

    Deliberately not filtered by step_id: reuse_key already encodes which
    skill ran and on what, so a step that hashes identically to a
    differently-named step in the source run is as reusable as one with
    the same id. reuse_key, not the workflow's naming, makes an output
    interchangeable (engine.step_hashing.reuse_key).
    """
    if source_run_id is None:
        return None
    row = session.scalar(
        select(RunStep)
        .where(RunStep.run_id == source_run_id)
        .where(RunStep.reuse_key == reuse_key)
        .where(RunStep.state == StepState.SUCCEEDED)
        .order_by(RunStep.position)
    )
    if row is None:
        return None
    runs_dir = get_paths(get_settings().data_dir).runs_dir
    run_output = read_run_output(runs_dir, source_run_id)
    if run_output is None or row.step_id not in run_output.steps:
        return None
    return row, run_output.steps[row.step_id]


def reuse_if_available(
    context: ExecutionContext, step: Step, row: RunStep, skills: SkillRegistry
) -> bool:
    """Adopt a source run's output for `step` if one matches, and say whether it did.

    The whole reuse branch of engine.preparation.execute_step, kept here so
    that file stays under the project's size limits and so the decision, the lookup
    and the adoption read as one thing in one place. False means there was
    nothing to reuse, and the caller runs the step as it always did.
    """
    reused = find_reusable_output(context.session, context.run.reused_from_run_id, row.reuse_key)
    if reused is None:
        return False
    source_row, output = reused
    # Validated like a freshly produced one: the skill
    # file the version names can have been edited since the source run (a
    # user's copy can change at any time), so "same skill_version"
    # is not proof the schema still holds.
    validated = validate_output(skills, step.skill, step.skill_version, output)
    skill = resolve_skill(skills, step.skill, step.skill_version)
    apply_reused_output(context, step, row, skill, source_row, validated)
    return True
