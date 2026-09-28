"""Reuse: rerunning only summarize, without transcription or diarization.

Two runs over the same recording: the first with a workflow naming skill
"s1" for its last step, the second with a *different* workflow: same "t"
(transcribe-like) and "d" (diarize-like) steps, but "s2" for the last one,
and it passes `--reuse-from` the first run's id. "t" and "d" must not run a
second time. "s" must, and must produce a new result. fakes.reuse_steps
carries the workflow shape and the counted fakes, shared with
test_engine_reuse_no_match.py.
"""

from __future__ import annotations

import pytest
from fakes.reuse_steps import install, workflow
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import RunStep
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.output import read_run_output


def _recording(session: Session) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="1" * 64,
        duration_seconds=1.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def _rows(session: Session, run_id: str) -> dict[str, RunStep]:
    result = session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
    return {row.step_id: row for row in result}


def test_a_different_final_step_is_recomputed_without_rerunning_upstream(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "d": 0, "s1": 0, "s2": 0}
    install(monkeypatch, calls)
    recording = _recording(db_session)

    created1 = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run1 = execute_run(db_session, created1.id, workflow=workflow("s1"))
    assert calls == {"t": 1, "d": 1, "s1": 1, "s2": 0}

    created2 = create_run(
        db_session,
        "test-workflow",
        "unpinned",
        recording_id=recording.id,
        reused_from_run_id=run1.id,
    )
    run2 = execute_run(db_session, created2.id, workflow=workflow("s2"))

    # transcribe and diarize did not run a second time.
    assert calls == {"t": 1, "d": 1, "s1": 1, "s2": 1}
    rows1, rows2 = _rows(db_session, run1.id), _rows(db_session, run2.id)
    assert rows2["t"].reused_from_run_id == run1.id
    assert rows2["d"].reused_from_run_id == run1.id
    # "s" itself has a different reuse_key (a different skill): recomputed.
    assert rows2["s"].reused_from_run_id is None

    # Provenance is inherited verbatim, never invented.
    assert (rows2["t"].model, rows2["t"].model_revision) == (
        rows1["t"].model,
        rows1["t"].model_revision,
    )
    assert (rows2["t"].provider, rows2["t"].host) == (rows1["t"].provider, rows1["t"].host)

    # The recomputed step produces a genuinely new result.
    runs_dir = get_paths(get_settings().data_dir).runs_dir
    output1 = read_run_output(runs_dir, run1.id)
    output2 = read_run_output(runs_dir, run2.id)
    assert output1 is not None and output1.steps["s"]["summary"] == "s1"
    assert output2 is not None and output2.steps["s"]["summary"] == "s2"
