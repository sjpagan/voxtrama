"""A step skipped by its condition consumed nothing: both hashes stay NULL.

Split from test_engine_step_hashing.py for the project's size limit, the same
reason test_engine_step_model_provenance.py gives for its own split. Uses
the same false-branch shape as test_engine_conditional.py: a 120s recording
against a `< 10` condition, so the branch is never taken and a step
depending on it never even reaches engine.preparation.execute_step.
"""

from __future__ import annotations

import pytest
from fakes.workflow import fake_skill
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.workflow.definition import Step, Workflow


def _recording(session: Session) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=120.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def _rows(session: Session, run_id: str) -> dict[str, RunStep]:
    result = session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
    return {row.step_id: row for row in result}


def _workflow() -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[
            Step(id="transcribe", skill="transcribe", skill_version="1.0.0"),
            Step(
                id="flag",
                skill="flag",
                skill_version="1.0.0",
                depends_on=["transcribe"],
                condition="recording.duration_seconds < 10",
            ),
        ],
    )


def test_a_step_skipped_by_its_condition_has_both_hashes_null(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _transcribe(ctx: ExecutionContext) -> dict:
        return {"language": "en"}

    def _must_not_run(ctx: ExecutionContext) -> dict:
        raise AssertionError("a skipped step must never run")

    monkeypatch.setattr(
        engine_run, "BUILTIN_STEPS", {"transcribe": _transcribe, "flag": _must_not_run}
    )
    monkeypatch.setattr(
        engine_run,
        "BUILTIN_SKILLS",
        {name: {"1.0.0": fake_skill(name)} for name in ("transcribe", "flag")},
    )

    recording = _recording(db_session)
    created = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run = execute_run(db_session, created.id, workflow=_workflow())

    rows = _rows(db_session, run.id)
    assert rows["flag"].state == StepState.SKIPPED
    assert rows["flag"].input_sha256 is None
    assert rows["flag"].reuse_key is None
    # transcribe itself ran and was not skipped: it does have both.
    assert rows["transcribe"].input_sha256 is not None
    assert rows["transcribe"].reuse_key is not None
