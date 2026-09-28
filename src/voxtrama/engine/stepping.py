"""What a single step's turn needs: whether to skip it, how to announce it, and the manifest.

Separate from run.py because that file owns the lifecycle of a Run (created,
executed, finished) and this owns what happens between the second and the
third. The loop that drives these across a workflow's steps, and catches an
engine fault while one of them is being handled, lives in engine.step_loop,
split out so this file stays under the project's size limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from voxtrama.config.settings import get_settings
from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep
from voxtrama.engine.activity_words import step_sentence
from voxtrama.engine.condition import evaluate_condition
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.progress_file import activity_reporter, publish_run_state
from voxtrama.engine.validation import UnknownSkillError, resolve_skill
from voxtrama.manifest.output import write_run_output
from voxtrama.manifest.writer import write_run_manifest
from voxtrama.workflow.condition import parse_condition
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.skill import ModelClass


@dataclass(frozen=True)
class StepFailure:
    """What stopped a run: the exception, and which step was running when it did.

    A tuple would do, but each side deserves a name: execute_run
    reads `.exc` to pick an error_code and `.step_id` to fill Run.error_step,
    and "the first element" is not a description of either.
    """

    exc: Exception
    step_id: str


@dataclass(frozen=True)
class SteppingTarget:
    """The six values every step-loop call needs about the run, not about any one step.

    Bundled so run_steps, its per-step helper and publish_manifest do not
    each thread their own copy of the same six-argument list. runs_dir, run
    and context are how a step talks to the world. rows, workflow and skills
    are what the manifest gets rewritten from.
    """

    runs_dir: Path
    run: Run
    context: ExecutionContext
    rows: list[RunStep]
    workflow: Workflow
    skills: SkillRegistry


def blocked_by_condition(step: Step, skipped: set[str], context: ExecutionContext) -> bool:
    """Whether `step` must be skipped: by its own condition, or one it depends on."""
    if any(dep in skipped for dep in step.depends_on):
        return True
    if step.condition is None:
        return False
    # Re-parsed here even though the loader already validated it, for the
    # same reason engine.steps re-checks depends_on: a workflow can reach
    # the engine from somewhere that never ran the loader.
    return not evaluate_condition(parse_condition(step.condition), context)


def _declared_ceiling(skills: SkillRegistry, step: Step) -> float | None:
    """The timeout a generative step is already granted, or None.

    Not "the elapsed time so far": a generative step is one blocking POST
    with no loop to measure a position from, so the only honest thing to
    publish is the ceiling it was already given. An elapsed count
    would need the engine to keep its own timer, which was decided
    against. An extractive step, or one whose
    skill the registry does not know yet (UnknownSkillError), gets None.
    """
    try:
        skill = resolve_skill(skills, step.skill, step.skill_version)
    except UnknownSkillError:
        return None
    if skill.model_class is not ModelClass.GENERATIVE:
        return None
    return get_settings().provider_timeout_seconds


def announce(target: SteppingTarget, total: int, position: int, step: Step) -> None:
    started_at = datetime.now(UTC).isoformat()  # The page counts elapsed time from it
    publish_run_state(
        target.runs_dir,
        target.run,
        step_total=total,
        step_index=position,
        step_id=step.id,
        message=step_sentence(step.id, step.skill),
        ceiling_seconds=_declared_ceiling(target.skills, step),
        step_started_at=started_at,
    )
    target.context.report_activity = activity_reporter(
        target.runs_dir, target.run, total, position, step.id, started_at
    )


def publish_manifest(target: SteppingTarget) -> None:
    """Rewrite the manifest: at the end of a step, and around the whole run.

    Public because engine.run calls this too, before the first step and
    after the last, so the two places a manifest is written from do not
    each carry a copy of the same call.
    """
    # output.json first, manifest second: the manifest's outputs[] entry
    # names a sha256, and that hash must belong to a file that already
    # exists by the time a reader can see it.
    digest = write_run_output(target.runs_dir, target.run.id, target.context.produced)
    write_run_manifest(
        target.runs_dir,
        target.run,
        target.rows,
        target.workflow,
        target.skills,
        target.context.recording,
        target.context.transcript,
        target.context.evidence,
        target.context.produced,
        output_digest=digest,
    )
