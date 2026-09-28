"""The run page, built from rows the route has already read.

Only the structure a page load can show without waiting on anything: a
run's state and its steps, each already `pending`, `running`,
`succeeded`, `failed` or `skipped` on its RunStep row.
engine.progress.record_planned_steps writes one row per step before any
of them runs, so an interrupted run still shows the steps it never
reached instead of looking shorter than it was. Where a step has
got to *inside itself* does not live here: that is progress.json's
shape (engine.progress_state), read live over SSE by
static/js/run_page.js. Reading progress.json here too would show the
same numbers twice (once from this render, once from the SSE message
that follows within api.routes.run_events.POLL_SECONDS of the page
opening) to save under half a second nobody can see. This module leaves
the position to whoever is watching live, the same way the run's overall
percentage is left to whoever displays it.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.db.models.run import Run, RunState, is_final
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.i18n.formatting import format_datetime, format_time
from voxtrama.i18n.translator import Translator
from voxtrama.logs.panel_line import PanelLine
from voxtrama.rendering.job_settings_line import JobHead
from voxtrama.rendering.run_failure import FailureBanner
from voxtrama.rendering.run_produced import ProducedView
from voxtrama.rendering.run_result import ResultView
from voxtrama.rendering.run_step_row import RunStepRow, resolved_step_rows
from voxtrama.workflow.definition import Step

# Same restraint as rendering.runs._STATE_TONE: only the two tones a
# vx-badge has ever needed get a name here. Marking a failed step is now
# the chain marker's job (components/_step_chain.scss's
# `[data-step-state="failed"]`, reading RunStepRow.state), so a third
# entry here would go unread. RunStepRow lives in rendering.run_step_row,
# split out to keep this file under the project's file-size limit.
_RUN_STATE_TONE = {RunState.SUCCEEDED: "success", RunState.RUNNING: "warning"}


@dataclass(frozen=True)
class RunPageView:
    """A run as GET /runs/{id}/view renders it on first paint, before any SSE message.

    `id` is what static/js/run_page.js reads off the page (a data
    attribute, not a second fetch) to build both the SSE URL and the
    GET /runs/{id}/vitality URL it polls on its own cadence.

    `step_states` and `run_states` are not about this run. They list every
    value StepState and RunState can take, in declaration order, so
    components/run_labels.html's `label_catalog()` renders one
    `{% trans %}`-translated label per state into the page. run_page.js
    reads that fixed dictionary instead of carrying its own English
    strings (a code review caught this: a live update that writes
    `event.state` straight into the DOM bypasses the translation catalogue,
    unnoticed while no non-English catalogue exists). Rendering the
    dictionary is the template's job. This only says which states exist.
    """

    id: str
    name: str
    workflow_name: str
    time: str
    state: str
    state_tone: str | None
    is_final: bool
    created_at: str
    steps: list[RunStepRow]
    step_states: list[str]
    run_states: list[str]
    step_progress_current: int
    step_progress_total: int
    # The terminal panel's first paint (empty while a run has no
    # run.log yet), and the failed-state banner/preview. Both None/empty
    # for a run that neither failed nor was interrupted.
    log_lines: list[PanelLine]
    # How many bytes of run.log `log_lines` already covers. It is the
    # `?last_event_id=` static/js/run_page.js puts on the SSE URL, so the
    # live connection resumes there instead of at 0.
    log_offset: int
    failure: FailureBanner | None
    produced: ProducedView | None
    # The transcript and extracted output a succeeded run leaves
    # behind. None for every other state, as `produced` is None for
    # anything but `failed`/`interrupted` above.
    result: ResultView | None
    # Title, settings line and «Regenerate job», for every state.
    head: JobHead | None = None


def run_page_view(
    run: Run,
    steps: list[RunStep],
    translator: Translator,
    filename: str | None = None,
    log_lines: list[PanelLine] | None = None,
    log_offset: int = 0,
    failure: FailureBanner | None = None,
    produced: ProducedView | None = None,
    result: ResultView | None = None,
    planned_workflow_steps: list[Step] | None = None,
    head: JobHead | None = None,
) -> RunPageView:
    """Build the page's initial view from a Run row and its RunStep rows, in position order.

    `run.state` is read into both `state` and the tone lookup. After a
    commit, SQLAlchemy's attribute expiry can return it as a plain `str`
    instead of a `RunState` (db.models.run.is_final's docstring explains
    why). A StrEnum's hash and equality match the plain string it wraps,
    so the dict lookup below works either way, as is_final relies on.

    `filename` is `Recording.original_filename`. The query that
    resolved `run.recording_id` ran in the route, the same division
    rendering.runs draws for the home page's Recent runs card: a presenter
    does not query. Run.label comes first. `name` falls back to
    `run.workflow_name` only when there is no Recording to name it after
    (a run whose import failed before one was created). No other source
    is tried, so a run's name depends only on the file someone recognises.
    `planned_workflow_steps` feeds resolved_step_rows.
    """
    step_rows, current, total = resolved_step_rows(steps, planned_workflow_steps)
    return RunPageView(
        id=run.id,
        name=run.label or filename or run.workflow_name,  # The job's own name first
        workflow_name=run.workflow_name,
        time=format_time(translator, run.created_at),
        state=str(run.state),
        state_tone=_RUN_STATE_TONE.get(run.state),
        is_final=is_final(run.state),
        created_at=format_datetime(translator, run.created_at),
        steps=step_rows,
        step_states=[state.value for state in StepState],
        run_states=[state.value for state in RunState],
        step_progress_current=current,
        step_progress_total=total,
        log_lines=log_lines or [],
        log_offset=log_offset,
        failure=failure,
        produced=produced,
        result=result,
        head=head,
    )
