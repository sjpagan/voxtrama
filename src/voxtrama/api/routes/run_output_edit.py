"""POST /runs/{id}/output/edit: correct one point of the verified output.

The form under each card of the Transcript tab (components/run_output.html):
the point (`ref`, manifest.edits' `<step>/<array>/<index>`), its new
`text`, and the turn it rests on (`turn`, "start:end" in seconds, one of
the job's own turns). Written to edits.json beside output.json, which
stays what the model produced (manifest.edits).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.config.paths import get_paths
from voxtrama.manifest.edits import point_at, write_edit
from voxtrama.manifest.output import read_run_output

router = APIRouter()

MAX_TEXT = 4000


def _refuse(detail: str) -> ProblemException:
    return ProblemException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_failed",
        title="That point cannot be changed this way",
        detail=detail,
    )


def _turn(raw: str) -> tuple[float, float] | None:
    """ "12.5:18" -> (12.5, 18.0); empty keeps the point's own evidence."""
    if not raw:
        return None
    start, _, end = raw.partition(":")
    try:
        pair = (float(start), float(end))
    except ValueError as exc:
        raise _refuse("the turn is not a time range") from exc
    if not 0 <= pair[0] < pair[1]:
        raise _refuse("the turn is not a time range")
    return pair


@router.post("/runs/{run_id}/output/edit")
async def edit_output_route(
    run_id: str, request: Request, session: DbDep, settings: SettingsDep
) -> RedirectResponse:
    """Record the correction, then reopen the Transcript tab."""
    run = get_run_or_404(run_id, session)
    runs_dir = get_paths(settings.data_dir).runs_dir
    output = read_run_output(runs_dir, run.id)
    form = await request.form()
    ref = str(form.get("ref") or "")
    if output is None or point_at(output, ref) is None:
        raise _refuse(f"this job has no point '{ref}'")
    text = str(form.get("text") or "").strip()
    if not text or len(text) > MAX_TEXT:
        raise _refuse(f"the text must be 1 to {MAX_TEXT} characters")
    edit: dict[str, object] = {"text": text}
    turn = _turn(str(form.get("turn") or ""))
    if turn is not None:
        edit["start"], edit["end"] = turn
    write_edit(runs_dir, run.id, ref, edit)
    return RedirectResponse(f"/runs/{run.id}/view?tab=transcript", status_code=303)
