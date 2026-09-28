"""Tests for the job_timeout an engine.run.create_run grants a Run.

Split from test_engine_run.py to stay under the file-length threshold: this
is one topic (a run's timeout), that one is the step-execution lifecycle.
The download/activity messages describe_if_timeout produces are their own
topic too, split out to test_engine_run_timeout_activity.py for the same
reason.
"""

from __future__ import annotations

import pytest
from rq.timeouts import JobTimeoutException
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow


def _workflow(*steps: Step) -> Workflow:
    return Workflow(
        name="test-workflow",
        version="2.1.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=list(steps),
    )


def _recording(session: Session, duration_seconds: float) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=duration_seconds,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def test_create_run_computes_a_job_timeout_from_its_recording(db_session: Session) -> None:
    recording = _recording(db_session, duration_seconds=600.0)
    created = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    assert created.job_timeout_seconds is not None
    assert created.job_timeout_seconds > 0


def test_create_run_without_a_recording_leaves_the_timeout_unset(db_session: Session) -> None:
    created = create_run(db_session, "test-workflow", "unpinned")
    assert created.job_timeout_seconds is None


def test_a_step_that_times_out_names_the_audio_and_the_granted_time(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With an artificially low timeout, the message names both numbers.

    RQ's own message, "Task exceeded maximum timeout value (N seconds)",
    says only what it enforced. A human needs the audio's duration too, to
    tell a wrong setting apart from audio that genuinely is that long.
    """

    def _times_out(ctx: ExecutionContext) -> None:
        raise JobTimeoutException("Task exceeded maximum timeout value (5 seconds)")

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"alpha": _times_out})
    recording = _recording(db_session, duration_seconds=600.0)
    created = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    # Artificially low, in place of the number create_run computed: the
    # point of this test is the message, not the sizing formula.
    created.job_timeout_seconds = 5
    db_session.flush()

    step = Step(id="first", skill="alpha", skill_version="1.0.0")
    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.FAILED
    assert run.error == "job timed out after 5s, granted for 600s of audio"
