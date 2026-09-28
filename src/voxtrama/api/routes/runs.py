"""GET /runs/{id} and GET /runs: read a run's state, steps, output, evidence.

state and error come from the Run row; steps from RunStep, ordered by
position; a step's own output from runs/<id>/output.json
(manifest.output); the evidence count from runs/<id>/manifest.json. The evidence count
could be recomputed by walking output.json instead, but the engine has
already counted it once and written that count to the manifest:
counting it again here would produce a second number for the same fact,
which is the duplication the project avoids by keeping manifest.json
and output.json separate files. This reads what is already there.

A run that failed is still read with 200: the request succeeded
even though the work it describes did not. Only a request itself can fail
here, and its taxonomy is closed to not_found, validation_failed on a bad
cursor or limit, and internal on a run artifact that is present but unreadable.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query, status
from pydantic import ValidationError
from sqlalchemy import select

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_cursor import after_cursor, decode_cursor, encode_cursor
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.api.run_views import RunDetail, RunPage, run_detail, run_summary
from voxtrama.config.paths import get_paths
from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep
from voxtrama.engine.superseded import superseded_steps
from voxtrama.manifest.evidence import ManifestEvidence
from voxtrama.manifest.output import RunOutput, read_run_output
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path

router = APIRouter()

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _internal_error(detail: str) -> ProblemException:
    """A run artifact that should be readable is not: a server fault.

    No stack trace in `detail` (the closed taxonomy forbids it). The run's
    own id is enough for an operator to find the broken file.
    """
    return ProblemException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal",
        title="A run artifact could not be read",
        detail=detail,
    )


def _read_output(runs_dir: Path, run_id: str) -> RunOutput | None:
    """read_run_output, with a present-but-invalid file turned into a 500."""
    try:
        return read_run_output(runs_dir, run_id)
    except ValidationError as exc:
        raise _internal_error(f"run {run_id} has an output.json that fails validation") from exc


def _read_evidence(runs_dir: Path, run_id: str) -> ManifestEvidence | None:
    """The manifest's evidence count, None when there is no manifest yet."""
    path = manifest_path(runs_dir, run_id)
    if not path.is_file():
        return None
    try:
        return Manifest.model_validate_json(path.read_bytes()).evidence
    except ValidationError as exc:
        raise _internal_error(f"run {run_id} has a manifest.json that fails validation") from exc


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, session: DbDep, settings: SettingsDep) -> RunDetail:
    """Return a run's full state (steps, output, evidence), always with 200."""
    run = get_run_or_404(run_id, session)
    steps = session.scalars(
        select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.position)
    ).all()
    runs_dir = get_paths(settings.data_dir).runs_dir
    output = _read_output(runs_dir, run_id)
    evidence = _read_evidence(runs_dir, run_id)
    superseded = superseded_steps(session, run, runs_dir)
    return run_detail(run, list(steps), output, evidence, superseded)


@router.get("/runs", response_model=RunPage)
def list_runs(
    session: DbDep,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    cursor: str | None = None,
) -> RunPage:
    """Return one page of runs, newest first, with an opaque cursor to the next.

    `limit`'s bounds are enforced by the Query constraint, not by hand: out
    of range is a 422 the RequestValidationError handler already renders in
    RFC 9457 (see api/errors.py), and the bound shows up in the generated
    OpenAPI schema instead of only living in this function's body.
    """
    query = select(Run).order_by(Run.created_at.desc(), Run.id.desc())
    if cursor is not None:
        query = query.where(after_cursor(decode_cursor(cursor)))
    rows = session.scalars(query.limit(limit + 1)).all()

    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = encode_cursor(page[-1]) if has_more else None
    return RunPage(items=[run_summary(run) for run in page], next_cursor=next_cursor)
