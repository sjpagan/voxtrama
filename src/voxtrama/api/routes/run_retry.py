"""POST /runs/{run_id}/retry: the failed-page banner's own "Retry this step".

The engine cannot restart one step in place: nothing resumes a Run that
already reached a final state. What it can start
is a fresh Run of the same workflow, on the same Recording,
told to reuse a source run's own succeeded steps (`reused_from_run_id`,
engine.enqueue.create_run). engine.reuse.find_reusable_output matches
by `reuse_key` (skill, skill_version, hardware_profile and an input hash),
so a step whose inputs and configuration have not changed since `run_id`
adopts its output outright instead of recomputing it, and only the step
that failed (and whatever came after it) runs again. In effect
this *is* "retry this step": from a person's own view, Ingest and
Transcribe stay done, and only Extract runs again. The button just does
not promise a surgical resume the engine has no way to perform.

One real gap this leaves: a memory failure's own retry is meant to
carry the tuning file's recommended values, one click, but
cores_per_chunk/parallel_chunks are Settings (a machine-wide file, not
anything a Run or RunChoices carries per-run: workflow.choices.RunChoices
has no such field), so this route has no per-run knob to set them on.
Retrying here reruns with whatever Settings already says. Changing that
is what "Open settings" leads to instead. Left as a known gap rather
than worked around with a field this run's shape does not have.

The model is api.routes.run_start: POST, then a 303 to the new run's own
page. Reloading a page that was itself a POST's result would resubmit it,
and there is no good answer to "confirm form resubmission" once a run has
already been enqueued a second time.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse

from voxtrama.api.deps import DbDep, QueueDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.api.routes.workflow_lookup import load_workflow_or_422
from voxtrama.db.models.run import Run, is_final
from voxtrama.db.people import local_user
from voxtrama.engine.enqueue import enqueue_run
from voxtrama.queue.errors import QueueUnavailable
from voxtrama.workflow.choices import RunChoices

router = APIRouter()


def _reject_unless_final(run: Run) -> None:
    """409: a run still going has nothing to retry yet, since it may still succeed."""
    if not is_final(run.state):
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            title="The run has not concluded",
            detail=f"Run {run.id} is still {run.state}",
        )


@router.post("/runs/{run_id}/retry")
def retry_run_route(run_id: str, session: DbDep, queue: QueueDep) -> RedirectResponse:
    """Enqueue a new Run of `run_id`'s own workflow, reusing what it already succeeded at."""
    run = get_run_or_404(run_id, session)
    _reject_unless_final(run)
    workflow = load_workflow_or_422(run.workflow_name)
    choices = RunChoices.model_validate(run.choices) if run.choices else None
    created_by = local_user(session).id
    try:
        new_run, _job_id = enqueue_run(
            session,
            queue,
            run.workflow_name,
            workflow,
            recording_id=run.recording_id,
            choices=choices,
            created_by=created_by,
            reused_from_run_id=run.id,
        )
    except QueueUnavailable as exc:
        raise ProblemException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="queue_unavailable",
            title="The queue is unavailable",
            detail=str(exc),
        ) from exc
    new_run.replaces_run_id = run.id  # The failed attempt goes once this succeeds
    session.commit()
    return RedirectResponse(f"/runs/{new_run.id}/view", status_code=status.HTTP_303_SEE_OTHER)
