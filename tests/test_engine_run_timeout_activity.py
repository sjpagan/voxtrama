"""Tests for the download/activity messages describe_if_timeout produces.

Split from test_engine_run_timeout.py to stay under the file-length
threshold: that file is the job_timeout budget itself, this is what a
timeout's message says once the activity channel is involved.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rq.timeouts import JobTimeoutException
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.progress_file import Activity, ProgressState, write_progress
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


def test_a_timeout_during_a_download_names_the_download_not_the_audio(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A run that dies fetching a model was never wrong about the audio.

    The step publishes a download in progress (the same call a real
    download makes through activity_reporter) right before the
    signal fires, so the progress file describe_if_timeout reads back is
    exactly what a genuine timeout mid-download would leave behind.
    """
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    def _times_out_mid_download(ctx: ExecutionContext) -> None:
        write_progress(
            get_paths(get_settings().data_dir).runs_dir,
            ProgressState(
                run_id=ctx.run.id,
                state="running",
                activity=Activity(
                    name="ASR model medium",
                    unit="bytes",
                    done=100 * 1024 * 1024,
                    total=500 * 1024 * 1024,
                ),
            ),
        )
        raise JobTimeoutException("Task exceeded maximum timeout value (5 seconds)")

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"alpha": _times_out_mid_download})
    recording = _recording(db_session, duration_seconds=600.0)
    created = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    created.job_timeout_seconds = 5
    db_session.flush()

    step = Step(id="first", skill="alpha", skill_version="1.0.0")
    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.FAILED
    assert run.error == (
        "job timed out after 5s while downloading ASR model medium: 400 MB of 500 MB still missing"
    )


def test_a_timeout_during_transcription_does_not_say_downloading(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The activity channel also carries a transcription's position:
    an activity mid-audio must not be mistaken for a download that never
    finished, or the message would send someone looking at the wrong thing.
    """
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    def _times_out_mid_audio(ctx: ExecutionContext) -> None:
        write_progress(
            get_paths(get_settings().data_dir).runs_dir,
            ProgressState(
                run_id=ctx.run.id,
                state="running",
                activity=Activity(name="audio", unit="seconds", done=300, total=600),
            ),
        )
        raise JobTimeoutException("Task exceeded maximum timeout value (5 seconds)")

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"alpha": _times_out_mid_audio})
    recording = _recording(db_session, duration_seconds=600.0)
    created = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    created.job_timeout_seconds = 5
    db_session.flush()

    step = Step(id="first", skill="alpha", skill_version="1.0.0")
    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.FAILED
    assert "downloading" not in run.error
    assert run.error == "job timed out after 5s, granted for 600s of audio"
