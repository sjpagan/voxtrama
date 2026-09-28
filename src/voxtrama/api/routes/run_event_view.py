"""RunEvent: the payload GET /runs/{id}/events sends on its `progress` events.

The route is promised, and so is that it closes, but not the
shape of what crosses the wire. Fixed here as a pydantic model rather than
in a comment, so it lands in the generated OpenAPI schema, for the same reason
as run_views.py for the JSON routes.

One event type only. No separate `end` event: `final: true` on this same
shape *is* the marker a run has finished. A second, empty event for the
same fact would be a second source for it, and EventSource reconnects on
its own once the server closes the stream, so a client that keeps
listening past `final: true` would reconnect forever onto a run that will
never say anything else. The client, not this route, is what has to close
the EventSource when it sees `final: true`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from voxtrama.db.models.run import Run, is_final
from voxtrama.engine.progress_state import Activity, ProgressState


class ActivityView(BaseModel):
    """engine.progress_state.Activity as the client reads it."""

    model_config = ConfigDict(extra="forbid")
    name: str
    unit: str
    done: float
    total: float | None


class RunEvent(BaseModel):
    """One `progress` SSE message: a ProgressState in full, plus whether it is the last one."""

    model_config = ConfigDict(extra="forbid")
    run_id: str
    state: str
    final: bool
    step_total: int
    step_index: int | None
    step_id: str | None
    message: str | None
    activity: ActivityView | None
    ceiling_seconds: float | None
    updated_at: str
    step_started_at: str | None = None  # The page's elapsed time counts from it


def _activity_view(activity: Activity | None) -> ActivityView | None:
    if activity is None:
        return None
    return ActivityView(
        name=activity.name, unit=activity.unit, done=activity.done, total=activity.total
    )


def run_event_from_progress(state: ProgressState) -> RunEvent:
    """Build the event from a ProgressState read off progress.json, mid-run."""
    return RunEvent(
        run_id=state.run_id,
        state=state.state,
        final=is_final(state.state),
        step_total=state.step_total,
        step_index=state.step_index,
        step_id=state.step_id,
        message=state.message,
        activity=_activity_view(state.activity),
        ceiling_seconds=state.ceiling_seconds,
        updated_at=state.updated_at,
        step_started_at=state.step_started_at,
    )


def run_event_from_run(run: Run) -> RunEvent:
    """Build the single event sent when a run is already final at connection time.

    Built from the Run row, not from progress.json: the database is the
    record of what happened (engine.progress_file.publish_run_state says so
    of itself), so a progress.json left behind from before the run
    concluded must not keep a client attached past a run that has already
    ended.
    """
    return RunEvent(
        run_id=run.id,
        state=str(run.state),
        final=True,
        step_total=0,
        step_index=None,
        step_id=None,
        message=None,
        activity=None,
        ceiling_seconds=None,
        updated_at=_last_known_timestamp(run),
    )


def _last_known_timestamp(run: Run) -> str:
    """The most specific truthful timestamp `run` has, for a final event's `id:`/`updated_at`.

    `finished_at` is what every real path to a final state sets
    (engine/run.py, engine/failure.py, engine/reconcile_close.py). A Run
    inserted straight into the database without going through one of them
    (a test row) may not have it. `started_at` is the next most specific
    fact, and `created_at` (mandatory on every Run) is the last resort.
    Never the wall clock: an event's timestamp is a fact about the run, not
    about when this route happened to answer.
    """
    when = run.finished_at or run.started_at or run.created_at
    return when.isoformat()
