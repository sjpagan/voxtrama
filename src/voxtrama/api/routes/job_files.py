"""GET /runs/{id}/transcript.{txt,md,json,jsonl}: a concluded job's full transcript.

The Files tab's single downloads, next to the whole package
(api.routes.job_package). The rows are the ones the Explore tab shows,
speaker names as corrected by hand included (rendering.transcript_files).
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import Response

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.api.routes.run_manifest_export import file_stem
from voxtrama.api.routes.run_page_result import result_view_for
from voxtrama.db.models.run import Run
from voxtrama.rendering.run_transcript import TranscriptRowView
from voxtrama.rendering.transcript_files import as_json, as_jsonl, as_markdown, as_text

router = APIRouter()

TYPES = {
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "json": "application/json",
    "jsonl": "application/x-ndjson",
}


def transcript_rows(session, settings, run: Run) -> tuple[TranscriptRowView, ...]:
    """The job's transcript rows; a 404 for a job with none (not concluded, or empty)."""
    result = result_view_for(session, settings, run)
    if result is None or not result.transcript:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="No transcript to export",
            detail=f"run '{run.id}' has no transcript",
        )
    return result.transcript


def render(fmt: str, title: str, rows: tuple[TranscriptRowView, ...]) -> str:
    if fmt == "md":
        return as_markdown(title, rows)
    if fmt == "jsonl":
        return as_jsonl(rows)
    return as_json(title, rows) if fmt == "json" else as_text(rows)


@router.get("/runs/{run_id}/transcript.{fmt}")
def transcript_file_route(run_id: str, fmt: str, session: DbDep, settings: SettingsDep) -> Response:
    """The whole transcript in `fmt`, as a download."""
    run = get_run_or_404(run_id, session)
    rows = transcript_rows(session, settings, run)
    if fmt not in TYPES:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="No transcript to export",
            detail=f"no transcript format '{fmt}'",
        )
    title = run.label or run.workflow_name
    return Response(
        render(fmt, title, rows),
        media_type=TYPES[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="{file_stem(run)}-transcript.{fmt}"'
        },
    )
