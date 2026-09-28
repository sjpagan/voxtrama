"""GET /runs/{id}/view serves the run page: the interior section a run's
own row in the home list, and its `id`, both now lead to.

The page was first meant to live at `GET /runs/{id}` itself. That exact
path belongs to the JSON resource this page's own JavaScript reads live
data from (api.routes.run_events, and this route's own initial render),
and two routes answering the same path with different content types is
not a form FastAPI's routing supports: the first one registered would
always win. So the page sits one segment under that path instead, here.
base.html's comment on root-relative asset links names this second depth.

Reads Run, RunStep and (for the name the page shows instead of its
workflow's) the one Recording row a run's own recording_id points
to, the same shape api.routes.runs.get_run already reads. It folds in
what a failed or interrupted run is worth showing on this same page
rather than a second one: its failure banner and what it did produce
before the step that failed (api.routes.run_page_failure), and does the
same for `succeeded`: its transcript and extracted output
(api.routes.run_page_result).

It also reads run.log (its last LOG_TAIL_LINES lines) and gives every
state the concluded job's head (api.routes.run_page_head). It takes `?tab=`
and `?merge=`. A replaced job's address leads on (api.routes.run_moved).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.routes.run_moved import run_or_moved
from voxtrama.api.routes.run_page_failure import failure_view_for, produced_view_for
from voxtrama.api.routes.run_page_head import job_head_for
from voxtrama.api.routes.run_page_planned_steps import planned_workflow_steps_for
from voxtrama.api.routes.run_page_result import ViewRequest, result_view_for
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import Settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import RunStep
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.logs.run_file import RUN_LOG_FILENAME
from voxtrama.logs.tail import tail_lines_with_offset
from voxtrama.rendering import (
    BackLink,
    Crumb,
    RunPageView,
    run_page_view,
    sidebar_items,
    stored_theme,
    theme_choices,
)

router = APIRouter()

# The live log shows around fifteen lines in view at once. 200
# is a generous scrollback above that, enough for a whole ASR pass on a
# short recording without turning this route into a read of the entire
# file every time someone opens the page (a run some hours in can have
# thousands of lines by then).
LOG_TAIL_LINES = 200


def _steps(session: Session, run_id: str) -> list[RunStep]:
    return list(
        session.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.position))
    )


def _filename(session: Session, recording_id: str | None) -> str | None:
    """`Recording.original_filename` for `recording_id`, or None."""
    if recording_id is None:
        return None
    recording = session.get(Recording, recording_id)
    return recording.original_filename if recording is not None else None


def _log_lines(settings: Settings, run_id: str) -> tuple[list[str], int]:
    """This page's own tail, plus how far into run.log it read.

    The offset is what static/js/run_page.js hands the SSE connection back
    as `?last_event_id=`, so run_log_stream.log_tail_for resumes exactly
    where this render stopped instead of resending it.
    """
    runs_dir = get_paths(settings.data_dir).runs_dir
    return tail_lines_with_offset(runs_dir / run_id / RUN_LOG_FILENAME, LOG_TAIL_LINES)


def _crumb_context(view: RunPageView) -> dict[str, object]:
    """Either `back_link` or `breadcrumb`: base.html renders only one of the two.

    A failed or interrupted run gets "← All runs", a concluded one
    nothing, a live one the breadcrumb.
    """
    if view.failure is not None:
        return {"back_link": BackLink(key="all-runs", href="/jobs")}
    if view.result is not None:
        return {}
    # The breadcrumb's own last ring is a piece of data (the run's
    # own name), not a fixed word, so it carries `label` rather than a
    # translated `key` (rendering.nav.Crumb's own docstring).
    return {"breadcrumb": [Crumb(key="runs", href="/jobs"), Crumb(key="run", label=view.name)]}


@router.get("/runs/{run_id}/view", response_class=HTMLResponse)
def run_page_route(
    run_id: str,
    translator: TranslatorDep,
    session: DbDep,
    settings: SettingsDep,
    tab: str | None = None,
    merge: float | None = None,
) -> HTMLResponse:
    """Render the run page inside base.html's interior-section layout (nav_items given)."""
    run = run_or_moved(run_id, session)
    failure = failure_view_for(run, settings)
    steps = _steps(session, run_id)
    log_lines, log_offset = _log_lines(settings, run_id)
    result = result_view_for(session, settings, run, ViewRequest(tab, merge))
    view = run_page_view(
        run,
        steps,
        translator,
        _filename(session, run.recording_id),
        log_lines=log_lines,
        log_offset=log_offset,
        failure=failure,
        produced=produced_view_for(session, run_id, settings) if failure else None,
        result=result,
        planned_workflow_steps=planned_workflow_steps_for(run, have_rows=bool(steps)),
        head=job_head_for(settings, run, result, session, translator),
    )
    context = page_context(
        session,
        translator,
        settings=settings,
        run=view,
        nav_items=sidebar_items("runs"),
        theme_choices=theme_choices(stored_theme(session)),
        origin=f"/runs/{run_id}/view",
        **_crumb_context(view),
    )
    template = templates_environment.get_template("pages/run.html")
    return HTMLResponse(template.render(**context))
