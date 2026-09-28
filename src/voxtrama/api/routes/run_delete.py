"""GET /runs/{id}/artifacts and DELETE /runs/{id}: dropping a run for good.

The home page only ever offers "View" on a run today. There is no way to
take one back, and `runs/<run_id>/` on disk (manifest.json, output.json,
run.log, progress.json, workflow.json) survives every path that exists.
`output.json` is not incidental: it holds the concepts, decisions and
citations a workflow extracted *from the recording's own words*, so
"Private storage" (your data stays with you) only half holds while a run a
person asked to delete still has that text sitting on disk.

**The Recording and its Transcript are a different layer, and this route
never touches either.** They cost more to reproduce than a run's own
artifacts, and `Run.reused_from_run_id` already means another run may have
been asked to reuse this one's steps. Deleting a run must not take the
audio, or a Transcript, out from under a run that still depends on it.

`GET .../artifacts` exists so a confirmation can say what
disappears instead of a bare "are you sure": it counts the run's own
directory rather than assuming the fixed five files above are always all
there: a run cancelled before `execute_run` ever started (run_cancel's own
`_close_never_started`) wrote none of them.

DELETE needs no exception to "resources, not actions" the way `cancel` does:
removing the resource itself is what a resource route means.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.errors import ProblemException
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.config.paths import get_paths
from voxtrama.db.models.run import Run, is_final
from voxtrama.db.models.step import RunStep

router = APIRouter()


class RunArtifacts(BaseModel):
    """What DELETE would remove from disk for one run."""

    model_config = ConfigDict(extra="forbid")
    file_count: int
    includes_extracted_text: bool


def _reject_unless_final(run: Run) -> None:
    """409: a run still going is stopped, not deleted: POST .../cancel first."""
    if not is_final(run.state):
        raise ProblemException(
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            title="The run has not concluded",
            detail=f"Run {run.id} is still {run.state}: cancel it before deleting it",
        )


def _run_directory(runs_dir: Path, run_id: str) -> Path | None:
    """The one directory this run may ever have written to, or None if it would not be.

    `run_id` here is always a value read back off the `Run` row DELETE
    already loaded through `get_run_or_404`. An id the request supplied
    can only reach this function by matching an existing row first,
    never concatenated into a path on its own. The containment check is
    the second line of defence, for a row whose `id` (a plain `String`
    column, the API contract has no rule that forbids it) was
    written by something other than `uuid.uuid4()`.
    """
    candidate = (runs_dir / run_id).resolve()
    if not candidate.is_relative_to(runs_dir.resolve()):
        return None
    return candidate


def _artifacts(run_dir: Path | None) -> RunArtifacts:
    """Count what is on disk, never the fixed five names assumed present."""
    if run_dir is None or not run_dir.is_dir():
        return RunArtifacts(file_count=0, includes_extracted_text=False)
    files = [entry for entry in run_dir.iterdir() if entry.is_file()]
    return RunArtifacts(
        file_count=len(files),
        includes_extracted_text=(run_dir / "output.json").is_file(),
    )


@router.get("/runs/{run_id}/artifacts", response_model=RunArtifacts)
def run_artifacts_route(run_id: str, session: DbDep, settings: SettingsDep) -> RunArtifacts:
    """What a confirmation should say is about to disappear, before it does."""
    run = get_run_or_404(run_id, session)
    runs_dir = get_paths(settings.data_dir).runs_dir
    return _artifacts(_run_directory(runs_dir, run.id))


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run_route(run_id: str, session: DbDep, settings: SettingsDep) -> None:
    """Remove `run_id`'s row, its steps, and its own directory, nothing else.

    The Recording and its Transcript are never touched here (see the
    module docstring). Steps first, then the run row, then the directory:
    if the directory removal ever raised, a request retried afterwards
    would still find a consistent database with nothing left to look up.
    """
    run = get_run_or_404(run_id, session)
    _reject_unless_final(run)
    # Read before the delete, not after: a session without expire_on_commit
    # disabled would otherwise try to reload an id off a row that no
    # longer exists once session.commit() below has run.
    deleted_run_id = run.id
    session.execute(delete(RunStep).where(RunStep.run_id == deleted_run_id))
    session.delete(run)
    session.commit()
    runs_dir = get_paths(settings.data_dir).runs_dir
    run_dir = _run_directory(runs_dir, deleted_run_id)
    if run_dir is not None and run_dir.is_dir():
        shutil.rmtree(run_dir)
