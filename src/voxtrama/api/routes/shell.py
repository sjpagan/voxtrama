"""GET / serves the home page: the new-job form and the last five jobs.

The home is no longer an upload box with a list of runs but the place
where a job is created: audio, workflow, name,
context and the `Advanced` options, then `Start job` (POST /jobs). The
status row left for the navbar's health pill; the upload gate
stays, because it is what decides whether `Start job` is offered
at all. Under the form, the last five jobs with `View all ›`.

`workflow` is the library's own «Run workflow» landing here with
the workflow it was chosen for: preselected if it names a workflow a job
can start on, silently dropped otherwise.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import exists, select

from voxtrama.api.deps import DbDep, EngineDep, SettingsDep
from voxtrama.api.routes.home_first_run import first_run_card
from voxtrama.api.routes.new_job_view import new_job_context
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.schema_check import check_schema
from voxtrama.diagnostics.readiness import read_readiness
from voxtrama.engine.catalog import list_workflow_names
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import (
    recent_activity_rows,
    sidebar_items,
    stored_theme,
    theme_choices,
    upload_gate,
)
from voxtrama.setup.wizard_start import FIRST_STEP_PATH, setup_pending

router = APIRouter()

# The home page shows a preview, not the full history ("Recent runs"
# isn't the runs list: see components/runs_list.html): a handful is
# enough to preview, and an unbounded list is a defect this project has
# already hit three times over.
RECENT_ACTIVITY_LIMIT = 5


def _recent_rows(session: DbDep, translator: TranslatorDep, workflow: str | None) -> list:
    """The merged `Recent runs` table: runs, plus recordings no run has touched yet.

    Split out of `shell` for the project's 40-line function limit when the
    upload gate joined the context: extracted rather than compressed, the same
    way rendering/nav.py gave up its Crumb.

    `workflow` travels through rather than being read here: it is the name
    the library sent along, and it belongs to the
    link a pending Recording's row builds, not to the query above it.
    """
    runs = session.scalars(
        select(Run).order_by(Run.created_at.desc()).limit(RECENT_ACTIVITY_LIMIT)
    ).all()
    # A row is named after the file someone recognises (rendering.runs'
    # own docstring), which lives on Recording, not Run. One query for
    # every recording these rows reference, rather than rendering.run_rows
    # querying per row (a presenter does not query).
    recording_ids = {run.recording_id for run in runs if run.recording_id}
    run_recordings = session.scalars(select(Recording).where(Recording.id.in_(recording_ids))).all()
    filenames = {recording.id: recording.original_filename for recording in run_recordings}

    # Imported, no Run started on it yet: the merged table below
    # still needs to show these, or an upload would vanish from the home
    # page the moment it lands, with nowhere left that shows it.
    pending_recordings = session.scalars(
        select(Recording)
        .where(~exists().where(Run.recording_id == Recording.id))
        .order_by(Recording.imported_at.desc())
        .limit(RECENT_ACTIVITY_LIMIT)
    ).all()
    labels = {run.id: run.label for run in runs if run.label}
    return recent_activity_rows(
        runs, pending_recordings, translator, filenames, RECENT_ACTIVITY_LIMIT, workflow, labels
    )


@router.get("/", response_class=HTMLResponse, response_model=None)
def shell(
    translator: TranslatorDep,
    session: DbDep,
    settings: SettingsDep,
    engine: EngineDep,
    workflow: str | None = None,
    accept_language: Annotated[str | None, Header()] = None,
) -> Response:
    """Render the new-job form and the last jobs, or send a first visit to the setup."""
    if setup_pending(settings.data_dir):
        return RedirectResponse(FIRST_STEP_PATH, status_code=303)
    readiness = read_readiness(settings)
    workflow = workflow if workflow in list_workflow_names() else None
    context = page_context(
        session,
        translator,
        settings=settings,
        nav_items=sidebar_items("home"),
        runs=_recent_rows(session, translator, workflow),
        gate=upload_gate(readiness, check_schema(engine)),
        first_run=first_run_card(settings, readiness),
        theme_choices=theme_choices(stored_theme(session)),
        origin="/",
        **new_job_context(settings, workflow, accept_language),
    )
    template = templates_environment.get_template("pages/home.html")
    return HTMLResponse(template.render(**context))
