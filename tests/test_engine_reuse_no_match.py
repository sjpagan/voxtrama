"""Two ways find_reusable_output legitimately finds nothing to reuse.

Both fall through to recomputing, the same answer engine.reuse.
find_reusable_output's own docstring names as always valid. No special
guard for either case, on purpose: a different recording's
reuse_key already differs because input_sha256 folds in recording_sha256,
and a failed source step is filtered out by find_reusable_output's own
`state == SUCCEEDED`.
"""

from __future__ import annotations

import pytest
from fakes.reuse_steps import install, workflow
from fakes.workflow import fake_skill
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import RunStep
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.workflow.definition import Step, Workflow


def _recording(session: Session, sha256: str) -> Recording:
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


def _rows(session: Session, run_id: str) -> dict[str, RunStep]:
    result = session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
    return {row.step_id: row for row in result}


def test_a_source_run_of_a_different_recording_reuses_nothing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "d": 0, "s1": 0, "s2": 0}
    install(monkeypatch, calls)
    first = _recording(db_session, "1" * 64)
    second = _recording(db_session, "2" * 64)

    created1 = create_run(db_session, "test-workflow", "unpinned", recording_id=first.id)
    run1 = execute_run(db_session, created1.id, workflow=workflow("s1"))
    created2 = create_run(
        db_session,
        "test-workflow",
        "unpinned",
        recording_id=second.id,
        reused_from_run_id=run1.id,
    )
    run2 = execute_run(db_session, created2.id, workflow=workflow("s1"))

    assert calls == {"t": 2, "d": 2, "s1": 2, "s2": 0}
    rows2 = _rows(db_session, run2.id)
    assert rows2["t"].reused_from_run_id is None
    assert rows2["d"].reused_from_run_id is None
    assert rows2["s"].reused_from_run_id is None


def _two_step_workflow() -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[
            Step(id="t", skill="t", skill_version="1.0.0"),
            Step(id="d", skill="d", skill_version="1.0.0", depends_on=["t"]),
        ],
    )


def _install_failing_d(monkeypatch: pytest.MonkeyPatch, calls: dict[str, int]) -> None:
    """Step "d" fails on its first call (the source run's own attempt) and succeeds after."""

    def _t(ctx: ExecutionContext) -> dict:
        calls["t"] += 1
        return {"value": "t"}

    def _d(ctx: ExecutionContext) -> dict:
        calls["d"] += 1
        if calls["d"] == 1:
            raise RuntimeError("d fails the first time, the source run's own attempt")
        return {"value": "d"}

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"t": _t, "d": _d})
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {name: {"1.0.0": fake_skill(name)} for name in ("t", "d")}
    )


def test_a_failed_step_in_the_source_run_is_not_reused(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "d": 0}
    _install_failing_d(monkeypatch, calls)
    recording = _recording(db_session, "3" * 64)
    small_workflow = _two_step_workflow()

    created1 = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run1 = execute_run(db_session, created1.id, workflow=small_workflow)
    assert run1.state == "failed"

    created2 = create_run(
        db_session,
        "test-workflow",
        "unpinned",
        recording_id=recording.id,
        reused_from_run_id=run1.id,
    )
    run2 = execute_run(db_session, created2.id, workflow=small_workflow)

    assert run2.state == "succeeded"
    assert calls == {"t": 1, "d": 2}
    rows2 = _rows(db_session, run2.id)
    assert rows2["t"].reused_from_run_id == run1.id
    assert rows2["d"].reused_from_run_id is None
