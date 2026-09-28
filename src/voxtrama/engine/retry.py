"""One step's attempts: how many, and recovery through a declared fallback.

Split from engine.stepping so the run loop stays about ordering and
skipping, and this stays about a single step's attempts and its on_error
policy.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.progress import mark_failed
from voxtrama.engine.timeout_message import describe_if_timeout
from voxtrama.workflow.definition import Step
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.skill import ModelClass

StepExecutor = Callable[[ExecutionContext, Step, RunStep], None]


def run_with_retry(
    context: ExecutionContext,
    step: Step,
    row: RunStep,
    execute: StepExecutor,
    skills: SkillRegistry,
) -> Exception | None:
    """Execute one step, retrying it only when that is safe.

    Retrying is sound for an extractive skill: a failed attempt consumed
    nothing, so trying again is as safe as running it the first time. A
    generative skill may have already produced something before it failed,
    and the engine cannot yet tell the two cases apart, so the retry is
    forbidden outright, whatever max_attempts the workflow
    declares. When the skill cannot even be resolved, the same caution
    applies: nothing here may assume a retry is safe without a positive
    answer.

    A skill overruling its workflow here is the general rule, not a special
    case. The skill declares what is always true of the capability, the
    workflow what holds for this run, and where they disagree the narrower
    one wins. A workflow asking for three attempts and getting one is that
    rule applied.
    """
    allowed = 1
    if _is_extractive(skills, step):
        allowed += step.on_error.retry.max_attempts

    last_exc: Exception | None = None
    for attempt in range(1, allowed + 1):
        row.attempts = attempt
        try:
            execute(context, step, row)
        except Exception as exc:  # noqa: BLE001 - retried or returned, never swallowed
            last_exc = exc
            continue
        return None
    return last_exc


def _is_extractive(skills: SkillRegistry, step: Step) -> bool:
    skill = skills.get(step.skill, {}).get(step.skill_version)
    return skill is not None and skill.model_class == ModelClass.EXTRACTIVE


def run_with_fallback(
    runs_dir: Path,
    run: Run,
    context: ExecutionContext,
    step: Step,
    row: RunStep,
    step_by_id: dict[str, Step],
    row_by_id: dict[str, RunStep],
    execute: StepExecutor,
    skills: SkillRegistry,
) -> tuple[Exception, str] | None:
    """Run `step`, and on failure its declared fallback, if it has one.

    `row` still ends up `failed` even when the fallback recovers it: it did
    fail, and saying otherwise would misreport what happened. The run only
    stops (with the (exception, step_id) returned here) if the fallback
    also fails, or there was none to try.
    """
    exc = run_with_retry(context, step, row, execute, skills)
    if exc is None:
        return None

    exc = describe_if_timeout(exc, run, context.recording, runs_dir)
    mark_failed(row, exc)
    fallback_id = step.on_error.fallback_step
    if fallback_id is None:
        return exc, step.id

    fallback_step = step_by_id[fallback_id]
    fallback_row = row_by_id[fallback_id]
    fb_exc = run_with_retry(context, fallback_step, fallback_row, execute, skills)
    if fb_exc is None:
        return None
    fb_exc = describe_if_timeout(fb_exc, run, context.recording, runs_dir)
    mark_failed(fallback_row, fb_exc)
    return fb_exc, fallback_step.id
