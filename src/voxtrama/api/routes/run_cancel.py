"""POST /runs/{id}/cancel: ask the queue to stop a run in progress.

The only action among the API's eight routes, by design: `cancel` is the
declared exception to "resources, not actions", not the first of many.

202 in every case that is not a request failure: the client
asked for a cancellation, it did not necessarily get a fact already
settled. A queued job can only be killed, not made to have never run, and
a killed process does not update its own Run, which is why 202
and not 200. Two shapes of `running`-or-earlier Run are handled
differently, both closing through engine.reconcile_close so neither path
disagrees with the other, or with engine.reconcile itself, about what a
cancelled Run says on the database or on disk:

* `pending`, or a Run with no job_id at all (see _close_never_started):
  nothing was ever running that could close this Run itself, so the
  route closes it right here, and writes nothing under runs_dir: no
  manifest or progress file exists yet for a Run that never reached
  execute_run.
* `running`: a worker is, or was, executing the job. The queue kills the
  process running it (queue.rq_backend.cancel), and the route closes the
  Run at once: a killed process never closes its own Run. So does a Run
  whose job the queue no longer knows (JobNotFound: RQ discards a job some
  time after it concludes, on its own TTL, the ordinary case under load).
  Both close through engine.reconcile_close.close_run, the same rewrite of
  the manifest and the progress file that reconcile_orphan_runs does for
  every other `running` Run it closes, because both already say `running`
  on disk and both need the same correction.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy.orm import Session

from voxtrama.api.deps import DbDep, QueueDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.api.run_views import RunSummary, run_summary
from voxtrama.config.paths import get_paths
from voxtrama.db.models.run import Run, RunState, is_final
from voxtrama.engine.reconcile_close import CANCELLED_ERROR_CODE, CANCELLED_MESSAGE, close_run
from voxtrama.queue.base import Queue
from voxtrama.queue.errors import JobNotFound, QueueUnavailable
from voxtrama.queue.job import JobId

router = APIRouter()


def _reject_if_already_concluded(run: Run) -> None:
    """409, not 202: a run already final has nothing left to cancel."""
    if not is_final(run.state):
        return
    raise ProblemException(
        status_code=status.HTTP_409_CONFLICT,
        code="conflict",
        title="The run is already concluded",
        detail=f"Run {run.id} is already {run.state}",
    )


def _cancel_on_queue_or_503(queue: Queue, job_id: str) -> bool:
    """Ask the queue to stop `job_id`. Returns True when there was nothing to stop.

    JobNotFound here is not a fault, and must not read as one (a 404 would
    be the tempting shape, and the wrong one): RQ discards a job some time
    after it concludes, on its own TTL, so a Run left `running` long
    enough for its job to be gone by the time someone tries to cancel it
    is the Run a user would want to cancel: the ordinary case
    under load, not a corner one. What the caller does with "nothing to
    stop" differs by the Run's own state, not by anything this function
    decides (see cancel_run_route).
    """
    try:
        queue.cancel(JobId(job_id))
    except JobNotFound:
        return True
    except QueueUnavailable as exc:
        raise ProblemException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="queue_unavailable",
            title="The queue is unavailable",
            detail=str(exc),
        ) from exc
    return False


def _close_never_started(session: Session, run: Run) -> None:
    """Mark `run` cancelled right now: it never had anything running to wait on.

    Reached whenever `run` was not `running` before this request: in
    practice only `pending`, since _reject_if_already_concluded has
    already turned away every final state. A `pending` Run never reached
    execute_run (whether or not it even has a job_id: one created before
    job ids were written up front has none, and is closed here the same way), so it
    has no manifest or progress file on disk yet (engine/run.py's own
    comment on where "the manifest exists" for the first time). There is
    nothing to rewrite. cancel_run_route decides by the Run's own prior
    state, not by whether a job_id happens to be null, because a `running`
    Run with no job_id (also possible, from the same earlier time) does have both files
    already, and closes through engine.reconcile_close.close_run instead.
    """
    run.state = RunState.CANCELLED
    run.finished_at = datetime.now(UTC)
    run.error_code = CANCELLED_ERROR_CODE
    run.error = CANCELLED_MESSAGE
    session.commit()


@router.post(
    "/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED, response_model=RunSummary
)
def cancel_run_route(
    run_id: str, session: DbDep, queue: QueueDep, settings: SettingsDep
) -> RunSummary:
    """Ask the queue to stop `run_id`, and close it here if nothing else will."""
    run = get_run_or_404(run_id, session)
    _reject_if_already_concluded(run)
    was_running = run.state == RunState.RUNNING
    if run.job_id is not None:
        _cancel_on_queue_or_503(queue, run.job_id)  # a running job is killed, a waiting one dropped
    if was_running:
        # Closed here, not at the next worker start: the queue has killed
        # the process running the job (queue.rq_backend.cancel), and a
        # killed process never closes its own Run. Waiting for a
        # reconciliation left the page saying «running».
        runs_dir = get_paths(settings.data_dir).runs_dir
        close_run(session, runs_dir, run, RunState.CANCELLED)
    else:
        _close_never_started(session, run)
    return run_summary(run)
