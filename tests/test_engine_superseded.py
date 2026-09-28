"""Rerunning transcription marks everything that depended on it.

Two runs over the same recording: the first the usual three-step shape
(fakes.reuse_steps), the second redoing the first step under skill "t2"
instead of "t": same recording, so the same input_sha256, but different
work, and a different step output on the same input supersedes directly.
Every step of the first run must come out superseded: "t" directly, "d"
and "s" by the cascade, the scenario the cascade is meant for.
test_engine_superseded_scope.py covers the negative cases: reuse, an
unrelated workflow, a different recording, run order.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes.reuse_steps import install, workflow
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.engine.superseded import superseded_steps


def _runs_dir() -> Path:
    """superseded_steps' new required parameter, unread here since
    every call below passes `workflow` explicitly. It only falls back to
    `runs_dir` when `workflow` is None.
    """
    return get_paths(get_settings().data_dir).runs_dir


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


def test_redoing_transcription_supersedes_every_downstream_step(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "t2": 0, "d": 0, "s1": 0, "s2": 0}
    install(monkeypatch, calls)
    recording = _recording(db_session)

    created_a = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run_a = execute_run(db_session, created_a.id, workflow=workflow("s1"))
    run_a.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.commit()

    created_b = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run_b = execute_run(db_session, created_b.id, workflow=workflow("s1", transcribe_skill="t2"))
    run_b.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    db_session.commit()

    result = superseded_steps(db_session, run_a, _runs_dir(), workflow=workflow("s1"))
    assert result == {"t": run_b.id, "d": run_b.id, "s": run_b.id}
    # run_b itself is the most recent thing that happened: nothing supersedes it.
    assert (
        superseded_steps(
            db_session, run_b, _runs_dir(), workflow=workflow("s1", transcribe_skill="t2")
        )
        == {}
    )


def test_reusing_a_run_does_not_supersede_it(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "t2": 0, "d": 0, "s1": 0, "s2": 0}
    install(monkeypatch, calls)
    recording = _recording(db_session)

    created_a = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run_a = execute_run(db_session, created_a.id, workflow=workflow("s1"))
    run_a.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.commit()

    created_b = create_run(
        db_session,
        "test-workflow",
        "unpinned",
        recording_id=recording.id,
        reused_from_run_id=run_a.id,
    )
    run_b = execute_run(db_session, created_b.id, workflow=workflow("s1"))
    run_b.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    db_session.commit()

    # Every step of run_b was adopted from run_a, same reuse_key throughout:
    # a reuse never supersedes the run it reused from.
    assert superseded_steps(db_session, run_a, _runs_dir(), workflow=workflow("s1")) == {}
