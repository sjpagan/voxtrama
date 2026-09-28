"""GET /runs/{id}/recap.{pdf,html,docx}: a concluded job's recap as a file.

The «Export» menu of the Recap tab (PDF, HTML, DOCX). The
recap is the one the tab shows (rendering.job_recap, through
api.routes.run_page_result), turned into blocks once
(rendering.recap_document) and written in the format asked for. Served
as an attachment named after the job, or a 404 for a job with no recap.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, status
from fastapi.responses import Response

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.api.routes.run_page_result import result_view_for
from voxtrama.api.templating import templates_environment
from voxtrama.i18n.dependency import TranslatorDep
from voxtrama.i18n.jinja import render_context
from voxtrama.i18n.translator import Translator
from voxtrama.rendering.recap_document import Block, recap_blocks, settings_text
from voxtrama.rendering.recap_docx import recap_docx
from voxtrama.rendering.recap_pdf import recap_pdf

router = APIRouter()

_TYPES = {
    "pdf": "application/pdf",
    "html": "text/html; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _words(translator: Translator) -> dict[str, str]:
    """The same msgids components/job_recap.html translates."""
    _ = translator.gettext
    return {
        "key_point": _("Key points"),
        "decision": _("Decisions"),
        "concept": _("Concepts"),
        "theme": _("Themes"),
        "needs_review": _("Needs review"),
    }


def _body(fmt: str, blocks: list[Block], title: str, translator: Translator) -> bytes:
    if fmt == "pdf":
        return recap_pdf(blocks)
    if fmt == "docx":
        return recap_docx(blocks)
    template = templates_environment.get_template("exports/recap.html")
    return template.render(title=title, blocks=blocks, **render_context(translator)).encode()


def _filename(title: str, fmt: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-") or "recap"
    return f"{stem}-recap.{fmt}"


@router.get("/runs/{run_id}/recap.{fmt}")
def recap_export_route(
    run_id: str, fmt: str, session: DbDep, settings: SettingsDep, translator: TranslatorDep
) -> Response:
    """The recap in `fmt`, as a download."""
    run = get_run_or_404(run_id, session)
    result = result_view_for(session, settings, run)
    if fmt not in _TYPES or result is None or not result.recap:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="not_found",
            title="No recap to export",
            detail=f"run '{run_id}' has no recap in format '{fmt}'",
        )
    title = run.label or run.workflow_name
    _ = translator.gettext
    meta = settings_text(result.settings, _("Detail"), _("cores"))
    blocks = recap_blocks(title, meta, result.recap, _words(translator))
    return Response(
        _body(fmt, blocks, title, translator),
        media_type=_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{_filename(title, fmt)}"'},
    )
