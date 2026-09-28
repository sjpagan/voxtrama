"""Pydantic response models for GET /runs and GET /runs/{id}.

Every field here has exactly one source, never two (see routes/runs.py's
own docstring for why): Run and RunStep rows from the database, output.json
via manifest.output, and manifest.json's own evidence count.

Lives in api/, not api/routes/: rendering.runs and
rendering.recent_activity both import RunSummary/run_summary from here,
and api/routes/__init__.py imports every router eagerly, so reaching into
that package for a response model with no route of its own turned
rendering's deliberate dependency on this type into a real import cycle
the first time voxtrama.rendering was imported on its own.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.manifest.evidence import ManifestEvidence
from voxtrama.manifest.output import RunOutput


class RunError(BaseModel):
    """Run.error as the client reads it. Never an HTTP error."""

    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    step: str | None


class StepView(BaseModel):
    """One RunStep row, as the client reads it."""

    model_config = ConfigDict(extra="forbid")
    step_id: str
    skill: str
    skill_version: str
    state: StepState
    position: int
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    # The run that superseded this step, or None when nothing has.
    # Informational only: a superseded step is still a correct result of
    # the run that produced it, so this blocks nothing and decides nothing
    # for the reader.
    superseded_by_run_id: str | None


class RunSummary(BaseModel):
    """A run as GET /runs's list renders it: no steps, no output."""

    model_config = ConfigDict(extra="forbid")
    id: str
    workflow_name: str
    workflow_version: str
    state: RunState
    recording_id: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunDetail(RunSummary):
    """A run as GET /runs/{id} returns it: everything the page shows."""

    error: RunError | None
    steps: list[StepView]
    # None only when there is no output.json yet. Never {}, which would
    # claim the run produced zero steps rather than not having run any.
    output: dict[str, dict[str, Any]] | None
    evidence: ManifestEvidence | None


class RunPage(BaseModel):
    """A page of GET /runs, ordered by created_at DESC then id DESC."""

    model_config = ConfigDict(extra="forbid")
    items: list[RunSummary]
    next_cursor: str | None


def step_view(row: RunStep, superseded_by_run_id: str | None) -> StepView:
    """Build a StepView from one RunStep row and its own superseded_by_run_id, if any."""
    return StepView(
        step_id=row.step_id,
        skill=row.skill,
        skill_version=row.skill_version,
        state=row.state,
        position=row.position,
        attempts=row.attempts,
        started_at=row.started_at,
        finished_at=row.finished_at,
        error=row.error,
        superseded_by_run_id=superseded_by_run_id,
    )


def run_summary(run: Run) -> RunSummary:
    """Build a RunSummary from one Run row."""
    return RunSummary(
        id=run.id,
        workflow_name=run.workflow_name,
        workflow_version=run.workflow_version,
        state=run.state,
        recording_id=run.recording_id,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def run_error(run: Run) -> RunError | None:
    """Build Run.error's client shape, or None when the run has not failed."""
    if run.state != RunState.FAILED:
        return None
    return RunError(code=run.error_code, message=run.error, step=run.error_step)


def run_detail(
    run: Run,
    steps: list[RunStep],
    output: RunOutput | None,
    evidence: ManifestEvidence | None,
    superseded: dict[str, str],
) -> RunDetail:
    """Assemble the full response of GET /runs/{id} from its five sources."""
    return RunDetail(
        id=run.id,
        workflow_name=run.workflow_name,
        workflow_version=run.workflow_version,
        state=run.state,
        recording_id=run.recording_id,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run_error(run),
        steps=[step_view(row, superseded.get(row.step_id)) for row in steps],
        output=output.steps if output is not None else None,
        evidence=evidence,
    )
