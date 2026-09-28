"""Tests for what engine.reconcile.reconcile_orphan_runs writes for a cancelled job.

Split from test_engine_reconcile_manifest.py, which covers the same disk
writes for the `interrupted` case. Kept apart so neither file grows past
the project's size limit. The state-level distinction itself (`cancelled` vs
`interrupted`) is checked in test_engine_reconcile.py. This only checks
that the distinction reaches disk too.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fakes.queue import InMemoryQueue, _JobRecord
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.run import Run, RunState
from voxtrama.engine.progress_file import read_progress
from voxtrama.engine.reconcile import reconcile_orphan_runs
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.queue.job import JobId, JobState, Progress


def _running_run(session: Session, *, job_id: str, workflow_name: str = "no-such-workflow") -> Run:
    run = Run(
        workflow_name=workflow_name,
        workflow_version="1.0.0",
        state=RunState.RUNNING,
        job_id=job_id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    session.commit()
    return run


def _set_job_state(queue: InMemoryQueue, job_id: str, state: JobState) -> None:
    queue._jobs[JobId(job_id)] = _JobRecord(state=state, progress=Progress(0, 0, ""))


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def test_a_cancelled_job_produces_a_manifest_and_progress_file_that_say_cancelled(
    db_session: Session, queue: InMemoryQueue
) -> None:
    """A run stopped on request must not read as `interrupted` on disk
    either: the same distinction test_engine_reconcile.py checks against
    `Run.state`, verified here against what a watcher and the manifest see.
    """
    run = _running_run(db_session, job_id="job-10")
    _set_job_state(queue, "job-10", JobState.CANCELLED)

    reconcile_orphan_runs(db_session, queue)

    state = read_progress(get_paths(get_settings().data_dir).runs_dir, run.id)
    assert state is not None
    assert state.state == "cancelled"
    manifest = _read_manifest(run.id)
    assert manifest.run.final is True
    assert manifest.failure is not None
    assert manifest.failure.code == "cancelled"
    assert manifest.failure.message == "cancelled on request"
