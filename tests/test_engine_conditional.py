"""A workflow with a conditional branch, run to completion.

engine.condition's own parsing and evaluation are tested in isolation in
tests/test_engine_condition.py. This is the whole shape:
two steps in sequence and a conditional branch, executed by the engine the
way `voxtrama run`'s worker does (execute_run), with every step's final
state readable back afterwards.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import RunStep, StepState
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill


def _workflow(*steps: Step) -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=list(steps),
    )


def _fake_skill(name: str) -> Skill:
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


def _steps_of(session: Session, run_id: str) -> dict[str, RunStep]:
    rows = session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
    return {row.step_id: row for row in rows}


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


def test_a_false_branch_is_skipped_and_a_step_depending_on_it_is_skipped_too(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _transcribe(ctx: ExecutionContext) -> dict:
        return {"language": "en"}

    def _must_not_run(ctx: ExecutionContext) -> dict:
        raise AssertionError("a skipped step must never run")

    monkeypatch.setattr(
        engine_run,
        "BUILTIN_STEPS",
        {"transcribe": _transcribe, "flag": _must_not_run, "summarize": _must_not_run},
    )
    monkeypatch.setattr(
        engine_run,
        "BUILTIN_SKILLS",
        {name: {"1.0.0": _fake_skill(name)} for name in ("transcribe", "flag", "summarize")},
    )

    recording = _recording(db_session, duration_seconds=120.0)
    created = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    workflow = _workflow(
        Step(id="transcribe", skill="transcribe", skill_version="1.0.0"),
        Step(
            id="flag",
            skill="flag",
            skill_version="1.0.0",
            depends_on=["transcribe"],
            # False for this 120s recording: the branch is never taken.
            condition="recording.duration_seconds < 10",
        ),
        Step(id="summarize", skill="summarize", skill_version="1.0.0", depends_on=["flag"]),
    )

    run = execute_run(db_session, created.id, workflow=workflow)

    assert run.state == JobState.SUCCEEDED
    rows = _steps_of(db_session, run.id)
    assert rows["transcribe"].state == StepState.SUCCEEDED
    assert rows["flag"].state == StepState.SKIPPED
    assert rows["summarize"].state == StepState.SKIPPED
