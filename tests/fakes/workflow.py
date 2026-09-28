"""Fakes for driving a workflow run end to end without real skills or a worker.

Used by test_cli_run_workflow.py to prove `voxtrama run` reaches `succeeded`
without downloading a model or transcribing audio.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from fakes.queue import InMemoryQueue
from voxtrama.db.models import Recording
from voxtrama.db.session import session_scope
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.run import execute_run
from voxtrama.queue.job import JobId
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill


def fake_skill(name: str) -> Skill:
    return Skill(
        name=name,
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=ModelClass.EXTRACTIVE,
        minimum_model_profile=ModelProfile.LOW,
        evidence_required=False,
        minimum_confidence=0.0,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )


# Stands in for both "transcribe" and "summarize": no output worth checking.
def fake_noop(ctx: ExecutionContext) -> dict:
    return {}


def fake_flag(ctx: ExecutionContext) -> dict:
    raise AssertionError("a skipped step must never run")


def fake_import_local_file(
    session: Session, source: Path, paths: object, created_by: str | None = None
) -> Recording:
    # Faked as in test_cli.py, to skip ffprobe. duration=120 keeps the branch false.
    recording = Recording(
        original_filename=source.name,
        stored_path=f"recordings/fake/{source.name}",
        content_sha256="0" * 64,
        duration_seconds=120.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


class SynchronousQueue(InMemoryQueue):
    """Runs the job body inline, as the RQ worker would out of process.

    submit() also captures the run_id, as _RecordingQueue does in test_cli.py.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        super().__init__()
        self._session_factory = session_factory
        self.submitted_run_ids: list[str] = []

    def submit(
        self, run_id: str, job_timeout: int | None = None, job_id: JobId | None = None
    ) -> JobId:
        self.submitted_run_ids.append(run_id)
        with session_scope(self._session_factory) as session:
            execute_run(session, run_id)
        return super().submit(run_id, job_timeout=job_timeout, job_id=job_id)
