"""Resolves a parsed Condition against a run's ExecutionContext.

Split from workflow.condition (the grammar and its parsing, no execution)
the same way engine.context is split from workflow.definition: the shape
of a condition is core. What feeds it is a run in progress,
and that belongs here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from voxtrama.db.models.step import StepState
from voxtrama.engine.context import ExecutionContext
from voxtrama.workflow.condition import STEPS_PATH, Condition, apply_operator


class ConditionEvaluationError(RuntimeError):
    """A condition names a step that has not produced anything yet."""


_SCALAR_RESOLVERS: dict[str, Callable[[ExecutionContext], Any]] = {
    "recording.duration_seconds": (
        lambda ctx: ctx.recording.duration_seconds if ctx.recording else None
    ),
    # "media_type" is the name workflow.condition's grammar exposes. The
    # column behind it is Recording.media_format: that column was named
    # before this condition surface existed, and renaming a populated
    # column is a migration not worth making for it.
    "recording.media_type": lambda ctx: ctx.recording.media_format if ctx.recording else None,
    "transcript.language": lambda ctx: ctx.transcript.language if ctx.transcript else None,
    "transcript.speaker_estimate": (
        lambda ctx: ctx.transcript.speaker_estimate if ctx.transcript else None
    ),
}


def evaluate_condition(condition: Condition, context: ExecutionContext) -> bool:
    """Whether `condition` holds for the current state of `context`."""
    actual = _resolve(condition.path, context)
    return apply_operator(condition, actual)


def _resolve(path: str, context: ExecutionContext) -> Any:
    scalar = _SCALAR_RESOLVERS.get(path)
    if scalar is not None:
        return scalar(context)
    match = STEPS_PATH.match(path)
    assert match is not None, "workflow.condition already rejected every other shape"
    step_id, key = match.group("step_id"), match.group("key")
    # Resolved before `produced`, not after: a failed step produced nothing,
    # and steps.<id>.state == "failed" (a case conditions exist to enable) must
    # still resolve instead of raising "has not produced anything yet".
    if key == "state":
        return _resolve_state(step_id, context)
    produced = context.produced.get(step_id)
    if produced is None:
        raise ConditionEvaluationError(
            f"condition references steps.{step_id}, which has not produced anything yet"
        )
    return produced.get(key)


def _resolve_state(step_id: str, context: ExecutionContext) -> StepState:
    """The final state of `step_id`, or raise if it has none yet.

    `pending` and `running` are not final: a condition that read either
    would compare true or false to something that has not happened yet, so
    this raises the same way an unresolved steps.<id>.<key> already does.
    """
    row = context.step_rows.get(step_id)
    if row is None or row.state in (StepState.PENDING, StepState.RUNNING):
        raise ConditionEvaluationError(
            f"condition references steps.{step_id}.state, which has not finished yet"
        )
    return row.state
