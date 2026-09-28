"""GET /jobs: the Jobs section, every job with its transcript.

The sidebar's first entry leads here: the whole list, newest first, no
filters, `New job` back to the home form, and each
row's ⋮ menu (Open, Regenerate, Delete...). Opening a job lands on its view.
Regenerate opens the job's view at the panel that reruns it (the job view
owns what a regeneration reuses).

`Delete...` needs no script: it links to `/jobs?delete=<id>`, and this route
renders the same page with the deletion dialog already open: the three
boxes Audio · Transcript · Recap, posted to
POST /jobs/{id}/delete (api.routes.job_delete). «Clean up» posts to
POST /jobs/prune, which comes back here with `?cleaned=<count>`.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.routes.new_job_view import job_workflow_titles
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import sidebar_items
from voxtrama.rendering.jobs import JobRow, job_rows

router = APIRouter()

PATH = "/jobs"


def _progress(session: Session, run_ids: list[str]) -> dict[str, tuple[int, int]]:
    """(steps finished, steps in all) per run, in one query."""
    done = RunStep.state.in_([StepState.SUCCEEDED, StepState.SKIPPED])
    finished = func.sum(case((done, 1), else_=0))
    rows = session.execute(
        select(RunStep.run_id, finished, func.count())
        .where(RunStep.run_id.in_(run_ids))
        .group_by(RunStep.run_id)
    )
    return {run_id: (int(done or 0), int(total)) for run_id, done, total in rows}


def all_job_rows(
    session: Session, translator: TranslatorDep, titles: dict[str, str]
) -> list[JobRow]:
    """Every job, newest first, as the table shows it."""
    runs = list(session.scalars(select(Run).order_by(Run.created_at.desc())))
    ids = {run.recording_id for run in runs if run.recording_id}
    recordings = {r.id: r for r in session.scalars(select(Recording).where(Recording.id.in_(ids)))}
    return job_rows(runs, recordings, _progress(session, [r.id for r in runs]), titles, translator)


@router.get(PATH, response_class=HTMLResponse)
def jobs_page(
    session: DbDep,
    settings: SettingsDep,
    translator: TranslatorDep,
    delete: str | None = None,
    cleaned: int | None = None,
) -> HTMLResponse:
    """The Jobs table. With `delete`, the same table with that job's deletion dialog open."""
    rows = all_job_rows(session, translator, job_workflow_titles(settings))
    deleting = next((row for row in rows if row.id == delete and row.final), None)
    context = page_context(
        session,
        translator,
        settings=settings,
        nav_items=sidebar_items("runs"),
        jobs=rows,
        deleting=deleting,
        cleaned=cleaned,
        origin=PATH,
    )
    return HTMLResponse(templates_environment.get_template("pages/jobs.html").render(**context))
