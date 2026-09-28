"""How far a run's steps have got, as a plain count.

Not the live `step_index`/`step_total` (engine.progress_state.
ProgressState): that pair only exists in progress.json, and only while a
run is live. rendering.run_page's docstring explains why the run page's
first render never reads that file. This is the fact that page needs
instead, derived from RunStep rows it already reads: which step a person
would point to as "the one going now", and how many there are in total.
The architecture leaves rendering nothing to calculate, not even a count,
so this lives here and not in rendering.run_page.
"""

from __future__ import annotations

from voxtrama.db.models.step import RunStep, StepState

_TERMINAL = frozenset({StepState.SUCCEEDED, StepState.FAILED, StepState.SKIPPED})


def step_progress(steps: list[RunStep]) -> tuple[int, int]:
    """(current_number, total): the step now running, or about to, one-based.

    `current_number` is how many steps are no longer pending, plus one for
    the step that count is waiting on, capped at `total` once every step
    has reached a terminal state, so a finished run reads "5 of 5", not
    "6 of 5". (0, 0) for a run with no steps yet.
    """
    total = len(steps)
    if total == 0:
        return 0, 0
    done = sum(1 for row in steps if row.state in _TERMINAL)
    return min(done + 1, total), total


def step_duration_seconds(step: RunStep) -> float | None:
    """How long `step` took, in seconds. None until it has both started and finished.

    The case for the rule in this module's docstring: a step's
    started_at/finished_at are real facts on the row, and the run page's
    failed-state chain (the "2 min" under each step) reads them here instead
    of subtracting two datetimes in rendering.run_page or in a template.
    """
    if step.started_at is None or step.finished_at is None:
        return None
    return (step.finished_at - step.started_at).total_seconds()
