"""POST /runs/{id}/segments/speaker: fix the speaker of one sentence.

The form behind each speaker chip of the job view (components/
speaker_fix.html): the segments of that bubble or row (`segment_id`,
repeated), and either a person already named on the recording
(`person_id`), a new name (`new_name`), or neither (back to the
detected speaker). db.segment_speaker does the work. A `person_id` that
is not one of this recording's own people is refused rather than linked.

Back to the tab the form came from (`tab`), the same plain after-POST
redirect api.routes.run_speaker_names ends on.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import DbDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.db.segment_speaker import assign_segments, speaker_choices
from voxtrama.rendering.run_result import TABS

router = APIRouter()


def _refuse(detail: str) -> ProblemException:
    return ProblemException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_failed",
        title="That speaker cannot be given to this sentence",
        detail=detail,
    )


@router.post("/runs/{run_id}/segments/speaker")
async def segment_speaker_route(run_id: str, request: Request, session: DbDep) -> RedirectResponse:
    """Give the posted segments the chosen speaker, then reopen the job view."""
    run = get_run_or_404(run_id, session)
    if run.recording_id is None:
        raise _refuse("this job has no recording left")
    form = await request.form()
    segment_ids = [str(value) for value in form.getlist("segment_id")]
    person_id = str(form.get("person_id") or "") or None
    new_name = str(form.get("new_name") or "")
    known = {pid for pid, _ in speaker_choices(session, run.recording_id)}
    if person_id is not None and person_id not in known:
        raise _refuse(f"'{person_id}' is not a speaker of this recording")
    if not assign_segments(session, run.recording_id, segment_ids, person_id, new_name):
        raise _refuse("none of those sentences belong to this job")
    tab = str(form.get("tab") or "")
    query = f"?tab={tab}" if tab in TABS else ""
    return RedirectResponse(f"/runs/{run_id}/view{query}", status_code=status.HTTP_303_SEE_OTHER)
