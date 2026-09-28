"""Tests for what engine.reconcile.reconcile_orphan_runs writes to disk.

Split from test_engine_reconcile.py, which covers which runs it closes.
Kept apart so neither file grows past the project's size limit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fakes.queue import InMemoryQueue, _JobRecord
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine.progress_file import read_progress
from voxtrama.engine.reconcile import reconcile_orphan_runs
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.queue.job import JobId, JobState, Progress


def _running_run(
    session: Session,
    *,
    job_id: str,
    workflow_name: str = "no-such-workflow",
    recording_id: str | None = None,
) -> Run:
    run = Run(
        workflow_name=workflow_name,
        workflow_version="1.0.0",
        state=RunState.RUNNING,
        job_id=job_id,
        recording_id=recording_id,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    session.commit()
    return run


def _recording(session: Session) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=42.0,
        media_format="wav",
    )
    session.add(recording)
    session.commit()
    return recording


def _set_job_state(queue: InMemoryQueue, job_id: str, state: JobState) -> None:
    queue._jobs[JobId(job_id)] = _JobRecord(state=state, progress=Progress(0, 0, ""))


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def test_the_manifest_of_an_interrupted_run_reloads_the_workflow_and_keeps_input(
    db_session: Session, queue: InMemoryQueue
) -> None:
    """The test that catches a reconciler writing a manifest from nothing
    instead of from what the database still knows: if `workflow` and
    `recording` were passed as None here, `definition_sha256` and `input`
    would both come back null even though the workflow shipped in the
    repository loads just fine and the Recording is still there to read.
    """
    recording = _recording(db_session)
    run = _running_run(
        db_session, job_id="job-7", workflow_name="transcribe-only", recording_id=recording.id
    )
    db_session.add(
        RunStep(
            run_id=run.id,
            step_id="transcribe",
            skill="transcribe",
            skill_version="1.0.0",
            state=StepState.SUCCEEDED,
            position=0,
        )
    )
    db_session.commit()
    _set_job_state(queue, "job-7", JobState.SUCCEEDED)

    closed = reconcile_orphan_runs(db_session, queue)

    assert closed == 1
    manifest = _read_manifest(run.id)
    assert manifest.run.final is True
    assert manifest.workflow.definition_sha256 is not None
    assert manifest.input is not None
    assert manifest.input.recording_id == recording.id
    assert manifest.input.duration_seconds == 42.0
    assert manifest.input.media_format == "wav"


def test_the_manifest_of_an_interrupted_run_says_why_it_ended(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run = _running_run(db_session, job_id="job-9")
    _set_job_state(queue, "job-9", JobState.FAILED)

    reconcile_orphan_runs(db_session, queue)

    manifest = _read_manifest(run.id)
    assert manifest.failure is not None
    assert manifest.failure.code == "interrupted"
    assert "no longer running" in manifest.failure.message


def test_the_progress_file_of_an_interrupted_run_stops_a_watcher_from_waiting(
    db_session: Session, queue: InMemoryQueue
) -> None:
    run = _running_run(db_session, job_id="job-8")
    _set_job_state(queue, "job-8", JobState.FAILED)

    reconcile_orphan_runs(db_session, queue)

    state = read_progress(get_paths(get_settings().data_dir).runs_dir, run.id)
    assert state is not None
    assert state.state == "interrupted"
