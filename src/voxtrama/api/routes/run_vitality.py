"""GET /runs/{id}/vitality: whether the worker behind a `running` Run still answers.

Its own route, not folded into GET /runs/{id}/events: that stream is
built to poll progress.json every POLL_SECONDS (run_events.py's own
constant) and must not also hit the queue backend that often. Redis is
cheap per call, not per call several times a second from every open tab.
The run page polls this route on its own, slower cadence instead (see
static/js/run_page.js), and only while a run is `running`: engine.vitality
has nothing to say about a Run that already has a final state.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from voxtrama.api.deps import DbDep, QueueDep
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.db.models.run import RunState
from voxtrama.engine.vitality import Vitality, run_vitality

router = APIRouter()


class VitalityView(BaseModel):
    """The one field GET /runs/{id}/vitality answers with."""

    model_config = ConfigDict(extra="forbid")
    vitality: Vitality


@router.get("/runs/{run_id}/vitality", response_model=VitalityView)
def run_vitality_route(run_id: str, session: DbDep, queue: QueueDep) -> VitalityView:
    """Ask the queue about `run_id`'s job, only when the Run is `running`.

    Any other state answers `alive` without touching the queue: a `pending`
    Run has no job a worker has picked up yet, which is not the same thing
    as one whose worker died on it, and a Run already final has nothing
    left to ask about. Either way there is no "worker gone" fact to
    report, so this never claims one.
    """
    run = get_run_or_404(run_id, session)
    if run.state != RunState.RUNNING:
        return VitalityView(vitality=Vitality.ALIVE)
    return VitalityView(vitality=run_vitality(queue, run.job_id))
