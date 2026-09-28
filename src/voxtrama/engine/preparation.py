"""Resolves a workflow into an executable order, and runs one step of it.

Split from run.py, which owns a Run's lifecycle (create it, run it, close
it), not how a single step executes or how a workflow's steps become an
order. Keeping the two apart also keeps run.py under the project's file
size limit.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep
from voxtrama.engine.anchoring import EvidenceNotAnchored, anchor_output
from voxtrama.engine.builtin import BUILTIN_SKILLS
from voxtrama.engine.catalog import load_named_workflow
from voxtrama.engine.choice_check import check_choices
from voxtrama.engine.context import ExecutionContext, StepFunction, build_context
from voxtrama.engine.diarize_choice import drop_declined_diarize
from voxtrama.engine.progress import mark_running, mark_succeeded, record_planned_steps
from voxtrama.engine.reuse import reuse_if_available
from voxtrama.engine.step_choices import apply_step_choices
from voxtrama.engine.step_hashing import record_step_hashes
from voxtrama.engine.steps import resolve_order
from voxtrama.engine.validation import UnknownSkillError, resolve_skill, validate_output
from voxtrama.logs import log_context
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.instructions import step_instructions
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.privacy import kept_local
from voxtrama.workflow.skill import Skill

logger = logging.getLogger(__name__)


def prepare_run(
    session: Session, run: Run, workflow: Workflow | None
) -> tuple[list[Step], list[RunStep], ExecutionContext, Workflow]:
    """Resolve the workflow into an order, plan its steps, build the context.

    Also returns the resolved Workflow itself: it names, versions and
    hashes the run's manifest, not only the order derived from it.
    """
    definition = workflow if workflow is not None else load_named_workflow(run.workflow_name)
    ordered = resolve_order(definition)
    context = build_context(session, run)
    # check_choices runs a second time here, against `definition`. This is
    # not a repeat of engine.enqueue.enqueue_run's call. That one
    # decides whether to *accept the request*, against the workflow the
    # caller resolved, and answers whoever made the request. This one
    # decides whether to *execute*, against the workflow prepare_run just
    # resolved from the catalogue, which can be a different file by now:
    # a user's copy in the data directory can be edited at any time, and a
    # Run sits queued between the two calls. A choice the workflow allowed
    # at acceptance can stop being allowed before the run starts.
    # ChoicesRejected then propagates up to fail_run instead of
    # applying a substitution the current workflow no longer permits.
    check_choices(context.choices, definition, BUILTIN_SKILLS)
    context.kept_local = kept_local(definition)
    # Dropped before step_skills is applied. check_choices has
    # already refused a diarize skip that another step depends on, so
    # nothing left in `ordered` is waiting on the step this removes.
    ordered = drop_declined_diarize(ordered, context.choices)
    ordered = apply_step_choices(ordered, context.choices)
    context.instructions = step_instructions(definition, ordered)
    # Replaces the "unpinned" placeholder the CLI writes before reading the file.
    run.workflow_version = definition.version
    rows = record_planned_steps(session, run, ordered)
    # Same objects as `rows`, not copies (see ExecutionContext.step_rows).
    context.step_rows = {row.step_id: row for row in rows}
    return ordered, rows, context, definition


def execute_step(
    context: ExecutionContext,
    step: Step,
    row: RunStep,
    builtin_steps: dict[str, StepFunction],
    skills: SkillRegistry,
) -> None:
    """Run one step, recording when it started and how it ended.

    Everything logged inside carries `step` alongside the run's id, through
    the logging context rather than an `extra` on each call.

    Reuse is decided right after record_step_hashes gives `row` its
    reuse_key: find_reusable_output looks for a matching succeeded step of
    context.run.reused_from_run_id, and a match's output goes to
    apply_reused_output instead of `implementation` ever running. No
    source run or no match falls through to running the step as before.
    """
    implementation = builtin_steps.get(step.skill)
    if implementation is None:
        raise UnknownSkillError(f"steps[{step.id}]: no implementation for skill '{step.skill}'")

    with log_context(step=step.id):
        context.current_step_id = step.id
        mark_running(context.session, row)
        # Before implementation() runs, not after: see
        # engine.step_hashing.record_step_hashes for why this moment.
        record_step_hashes(context, step, row)
        logger.info("step started")
        if not reuse_if_available(context, step, row, skills):
            # implementation() runs before any skill is resolved: a step
            # failing on its own must fail on that.
            output = implementation(context)
            validated = validate_output(skills, step.skill, step.skill_version, output)
            skill = resolve_skill(skills, step.skill, step.skill_version)
            _finish_step(context, step, row, skill, validated)
        logger.info("step finished")


def _finish_step(
    context: ExecutionContext, step: Step, row: RunStep, skill: Skill, output: dict[str, Any]
) -> None:
    """Anchor, publish and mark succeeded: the tail every freshly-run step shares.

    Split out of execute_step for the project's line limit. A reused step's
    tail is engine.reuse.apply_reused_output instead, which also inherits
    provenance and loads the transcript.
    """
    try:
        context.evidence[step.id] = anchor_output(skill, context.transcript, output)
    except EvidenceNotAnchored as exc:
        # The count must reach the manifest even though this step fails:
        # recorded before the exception re-raises, unchanged.
        context.evidence[step.id] = exc.count
        raise
    context.produced[step.id] = output
    mark_succeeded(context.session, row)
