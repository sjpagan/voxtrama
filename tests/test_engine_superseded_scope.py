"""Where engine.superseded.superseded_steps must stay silent.

Three ways a later run on the same recording must *not* mark an earlier
one superseded (a workflow that does not redo anything
differently, a run of a different recording entirely, and a run that
merely happens to be older), plus the direction check that makes the last
one meaningful. test_engine_superseded.py covers the positive case: a
redone transcription cascading onto everything that depended on it.
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
from voxtrama.workflow.definition import Step, Workflow


def _runs_dir() -> Path:
    """superseded_steps' new required parameter, unread here since
    every call below passes `workflow` explicitly. It only falls back to
    `runs_dir` when `workflow` is None.
    """
    return get_paths(get_settings().data_dir).runs_dir


def _recording(session: Session, sha256: str = "1" * 64) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256=sha256,
        duration_seconds=1.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def _single_step_workflow() -> Workflow:
    """Just "t", same skill and version run_a itself used: no "d", no "s"."""
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="t", skill="t", skill_version="1.0.0")],
    )


def test_a_workflow_that_redoes_nothing_differently_supersedes_nothing(
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
    run_b = execute_run(db_session, created_b.id, workflow=_single_step_workflow())
    run_b.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    db_session.commit()

    # Same skill, same version: run_b's "t" is the identical work, not a
    # derivation, and it never touched "d" or "s" at all.
    assert superseded_steps(db_session, run_a, _runs_dir(), workflow=workflow("s1")) == {}


def test_a_run_of_a_different_recording_supersedes_nothing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "t2": 0, "d": 0, "s1": 0, "s2": 0}
    install(monkeypatch, calls)
    first = _recording(db_session, "1" * 64)
    second = _recording(db_session, "2" * 64)

    created_a = create_run(db_session, "test-workflow", "unpinned", recording_id=first.id)
    run_a = execute_run(db_session, created_a.id, workflow=workflow("s1"))
    run_a.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.commit()

    created_b = create_run(db_session, "test-workflow", "unpinned", recording_id=second.id)
    run_b = execute_run(db_session, created_b.id, workflow=workflow("s1", transcribe_skill="t2"))
    run_b.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    db_session.commit()

    assert superseded_steps(db_session, run_a, _runs_dir(), workflow=workflow("s1")) == {}


def test_an_older_run_never_supersedes_a_newer_one(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "t2": 0, "d": 0, "s1": 0, "s2": 0}
    install(monkeypatch, calls)
    recording = _recording(db_session)

    created_new = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run_new = execute_run(db_session, created_new.id, workflow=workflow("s1"))
    run_new.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    db_session.commit()

    created_old = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    old_workflow = workflow("s1", transcribe_skill="t2")
    run_old = execute_run(db_session, created_old.id, workflow=old_workflow)
    run_old.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.commit()

    # run_old's "t" differs from run_new's, but run_old is the *earlier*
    # one on the timeline: order, not insertion sequence, decides.
    assert superseded_steps(db_session, run_new, _runs_dir(), workflow=workflow("s1")) == {}
    assert superseded_steps(db_session, run_old, _runs_dir(), workflow=old_workflow) == {
        "t": run_new.id,
        "d": run_new.id,
        "s": run_new.id,
    }
