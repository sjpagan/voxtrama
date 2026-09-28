"""RunStepRow: one RunStep as the run page's step chain shows it.

Split out of rendering.run_page to keep that file under the project's file
limit. This is the part that changed shape once the chain's body got a
duration line to show.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.step_progress import step_progress
from voxtrama.rendering.run_step_outcome import duration_parts
from voxtrama.workflow.definition import Step

# Same restraint as rendering.runs._STATE_TONE: only the two tones a
# vx-badge has ever needed get a name here. Marking a failed step is now
# the chain marker's job (components/_step_chain.scss's
# `[data-step-state="failed"]`, reading RunStepRow.state), so a third
# entry here would go unread.
_STEP_STATE_TONE = {StepState.SUCCEEDED: "success", StepState.RUNNING: "warning"}


@dataclass(frozen=True)
class RunStepRow:
    """One RunStep as the page's step chain shows it.

    `label` is `step_id` with underscores and hyphens turned into spaces
    and each word capitalised ("extract_decisions" -> "Extract Decisions").
    A person reads the workflow's step id, not `skill`, which names
    the implementation behind it and can differ from what a step is *for*
    ("diarize" behind a step called "Speakers"). A formatting choice, not
    a new fact: `step_id` is the same string `data-step-id` carries, just
    no longer read as an identifier.

    `duration_minutes`/`duration_short` are None/False for a step never
    both started and finished. See rendering.run_step_outcome.
    duration_parts for what "short" means.
    """

    step_id: str
    label: str
    skill: str
    state: str
    tone: str | None
    duration_minutes: int | None
    duration_short: bool
    # Adopted from the job it was regenerated from, not run again.
    reused: bool = False


def _humanize_step_id(step_id: str) -> str:
    return " ".join(word.capitalize() for word in step_id.replace("-", "_").split("_"))


def planned_step_rows(steps: list[Step]) -> list[RunStepRow]:
    """`steps`, all `pending`: the chain a run shows before any RunStep
    row exists.

    api.routes.run_page reads this only right after `Start run`'s
    redirect. engine.progress.record_planned_steps writes the real rows a
    beat after the worker picks the job up, and a person landing on the
    page in that gap used to see no chain at all.
    static/js/run_page.js's applyStepChain() only updates `[data-step-id]`
    elements already in the DOM and never adds one, so an empty first
    render stayed empty until the run reached a final state and the page
    reloaded (measured on a real run: [data-step-id] absent from the DOM
    for 32 seconds while RunStep already held three rows).

    Once a real RunStep row exists for a step, that row wins and this is
    never consulted again for that run. A step skipped by its condition
    is a fact only the database holds. This function cannot know it and
    does not try (every row here reads "pending", unconditionally).
    """
    return [
        RunStepRow(
            step_id=step.id,
            label=_humanize_step_id(step.id),
            skill=step.skill,
            state=str(StepState.PENDING),
            tone=None,
            duration_minutes=None,
            duration_short=False,
        )
        for step in steps
    ]


def resolved_step_rows(
    steps: list[RunStep], planned_workflow_steps: list[Step] | None
) -> tuple[list[RunStepRow], int, int]:
    """The chain rows to show, plus (current, total). Real RunStep rows
    when there are any, `planned_step_rows` of `planned_workflow_steps`
    when there are none yet (planned_step_rows's docstring says why that
    gap exists and why a real row always wins once one does).

    `current`/`total` for the planned-only branch is `(1, count)`: no step
    has started, so the one "now running or about to" (engine.step_progress.
    step_progress's phrase) is the first. That function would give the
    same answer for all-pending RunStep rows, without needing rows that
    do not exist yet.
    """
    ordered = sorted(steps, key=lambda row: row.position)
    if ordered:
        current, total = step_progress(ordered)
        return [step_row(row) for row in ordered], current, total
    planned = planned_step_rows(planned_workflow_steps or [])
    return planned, (1 if planned else 0), len(planned)


def step_row(row: RunStep) -> RunStepRow:
    # str(), not .value: the same post-commit attribute-expiry tolerance
    # run_page_view's docstring explains for Run.state. RunStep.state is
    # the same kind of column.
    duration_minutes, duration_short = duration_parts(row)
    return RunStepRow(
        step_id=row.step_id,
        label=_humanize_step_id(row.step_id),
        skill=row.skill,
        state=str(row.state),
        tone=_STEP_STATE_TONE.get(row.state),
        duration_minutes=duration_minutes,
        duration_short=duration_short,
        reused=row.reused_from_run_id is not None,
    )
