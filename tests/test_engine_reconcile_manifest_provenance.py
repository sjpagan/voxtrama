"""reconcile_orphan_runs' manifest keeps the five provenance fields.

Split from test_engine_reconcile_manifest.py to stay under the project's
file size limit: same helpers, one more concern. reconcile_orphan_runs never
has a live ExecutionContext (the process that had one is gone), so this
proves the manifest still carries model, model_revision, provider, host
and profile_check_skipped from the RunStep row alone, which is why the
row stores them.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fakes.queue import InMemoryQueue, _JobRecord
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.reconcile import reconcile_orphan_runs
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.queue.job import JobId, JobState, Progress


def _running_run(session: Session, *, job_id: str) -> Run:
    run = Run(
        workflow_name="no-such-workflow",
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


def test_a_reconciled_runs_manifest_keeps_the_five_voci_with_no_context_at_all(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run = _running_run(db_session, job_id="job-10")
    db_session.add(
        RunStep(
            run_id=run.id,
            step_id="summarize",
            skill="summarize",
            skill_version="1.0.0",
            state=StepState.SUCCEEDED,
            position=0,
            model="qwen-test",
            model_revision="sha256:x",
            provider="ollama",
            host="127.0.0.1:11434",
            profile_check_skipped=False,
        )
    )
    db_session.commit()
    _set_job_state(queue, "job-10", JobState.SUCCEEDED)

    reconcile_orphan_runs(db_session, queue)

    manifest = _read_manifest(run.id)
    step = manifest.steps[0]
    assert (step.model, step.model_revision) == ("qwen-test", "sha256:x")
    assert (step.provider, step.host) == ("ollama", "127.0.0.1:11434")
    assert step.profile_check_skipped is False
