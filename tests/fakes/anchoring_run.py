"""Drives a real engine run for calibration.anchoring's own tests.

Shared by test_calibration_anchoring.py and
test_calibration_anchoring_missing.py: both need a run built by
engine.run.execute_run, never a hand-written output.json (see
calibration/anchoring.py's own module docstring on why), and duplicating
the monkeypatching and workflow wiring in two files would make the same
shape of change twice.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill

TRANSCRIPT_TEXT = "hello there"


def fake_skill(name: str) -> Skill:
    return Skill(
        name=name,
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=ModelClass.GENERATIVE,
        minimum_model_profile=ModelProfile.LOW,
        evidence_required=False,
        minimum_confidence=0.0,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )


def fake_transcript() -> Transcript:
    built = Transcript(
        id="t1",
        recording_id="r1",
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="low",
    )
    built.segments = [Segment(start=0.0, end=2.0, text=TRANSCRIPT_TEXT, confidence=1.0)]
    return built


def _implementation(spec: dict) -> Callable[[ExecutionContext], dict]:
    """One step's own BUILTIN_STEPS entry: returns spec["output"], or raises if spec["fails"]."""

    def _run(ctx: ExecutionContext) -> dict:
        ctx.transcript = fake_transcript()
        if spec.get("fails"):
            raise RuntimeError("step fails on purpose, for calibration.anchoring's own tests")
        return spec["output"]

    return _run


def run_workflow(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, steps: dict[str, dict]
) -> str:
    """Execute a workflow whose steps map step_id -> {skill, output} or {skill, fails: True}.

    A failing step never reaches _finish_step (engine.preparation): its
    step_id lands in manifest.steps (state "failed", engine.failure) but
    not in output.json's own steps, the real shape that
    calibration.anchoring's skipped_steps case measures against.
    """
    builtin_steps: dict[str, Callable] = {}
    builtin_skills: dict[str, dict] = {}
    workflow_steps = []
    for step_id, spec in steps.items():
        skill_name = spec["skill"]
        # Keyed by skill, not step_id: engine.preparation.execute_step
        # resolves an implementation off step.skill (one step per skill in
        # every case here, so the two never collide).
        builtin_steps[skill_name] = _implementation(spec)
        builtin_skills.setdefault(skill_name, {})["1.0.0"] = fake_skill(skill_name)
        workflow_steps.append(Step(id=step_id, skill=skill_name, skill_version="1.0.0"))

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", builtin_steps)
    monkeypatch.setattr(engine_run, "BUILTIN_SKILLS", builtin_skills)
    workflow = Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=workflow_steps,
    )
    created = create_run(db_session, "test-workflow", "unpinned")
    execute_run(db_session, created.id, workflow=workflow)
    return created.id
