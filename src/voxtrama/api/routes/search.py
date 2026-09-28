"""GET /search: the navbar's search.

It searches **only** the text of finished transcripts and the titles of
jobs, never outputs, workflows or settings. Results come
grouped by job with every occurrence under it (rendering.search_results).

A plain case-insensitive LIKE on the database the product already uses,
no new service. A local installation holds
hours of audio, not millions of documents, and a scan of its segments
answers in milliseconds. A full-text index can come the day a measurement
says it is needed. `%` and `_` in the query are escaped, so they are
searched for as the characters someone typed.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.routes.new_job_view import job_workflow_titles
from voxtrama.api.templating import page_context, templates_environment
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.rendering import sidebar_items
from voxtrama.rendering.search_results import SearchGroup, search_groups

router = APIRouter()

MIN_QUERY_LENGTH = 2
MAX_HITS = 500


def _pattern(query: str) -> str:
    escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _job_names(session: Session, runs: list[Run]) -> dict[str, str]:
    ids = {run.recording_id for run in runs if run.recording_id}
    files = dict(
        session.execute(
            select(Recording.id, Recording.original_filename).where(Recording.id.in_(ids))
        ).all()
    )
    return {run.id: run.label or files.get(run.recording_id, run.workflow_name) for run in runs}


def find(session: Session, query: str, titles: dict[str, str], translator) -> list[SearchGroup]:
    """Every job whose transcript or title contains `query`, with its occurrences."""
    pattern = _pattern(query)
    hits = session.execute(
        select(Segment, Run)
        .join(Transcript, Segment.transcript_id == Transcript.id)
        .join(Run, Run.id == Transcript.produced_by_run_id)
        .where(func.lower(Segment.text).like(pattern, escape="\\"))
        .order_by(Run.created_at.desc(), Segment.start)
        .limit(MAX_HITS)
    ).all()
    title_matches = list(
        session.scalars(
            select(Run)
            .outerjoin(Recording, Recording.id == Run.recording_id)
            .where(
                or_(
                    func.lower(Run.label).like(pattern, escape="\\"),
                    func.lower(Recording.original_filename).like(pattern, escape="\\"),
                )
            )
        )
    )
    runs = [run for _, run in hits] + title_matches
    names = _job_names(session, runs)
    return search_groups(query, list(hits), title_matches, names, titles, translator)


@router.get("/search", response_class=HTMLResponse)
def search_page(
    session: DbDep, settings: SettingsDep, translator: TranslatorDep, q: str = ""
) -> HTMLResponse:
    """Results for `q`, grouped by job. Nothing is searched under two characters."""
    query = q.strip()
    long_enough = len(query) >= MIN_QUERY_LENGTH
    groups = find(session, query, job_workflow_titles(settings), translator) if long_enough else []
    template = templates_environment.get_template("pages/search.html")
    context = page_context(
        session,
        translator,
        settings=settings,
        nav_items=sidebar_items("runs"),
        search_query=query,
        search_too_short=bool(query) and not long_enough,
        groups=groups,
        match_count=sum(len(group.hits) for group in groups),
        origin="/search",
    )
    return HTMLResponse(template.render(**context))
