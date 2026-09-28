"""announce() publishes a generative step's declared ceiling, and nothing else's.

A generative step is one blocking call with no loop to measure a position
from, so the only honest thing the engine can publish is the timeout it was
already granted, never an elapsed count it would have to keep on its own.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.models.run import Run, RunState
from voxtrama.engine.builtin import TRANSCRIBE
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.progress_file import read_progress
from voxtrama.engine.stepping import SteppingTarget, announce
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.skill import ModelClass

GENERATIVE_SKILL = TRANSCRIBE.model_copy(
    update={"name": "alpha", "model_class": ModelClass.GENERATIVE}
)


def _target(runs_dir: Path, db_session: Session) -> SteppingTarget:
    run = Run(id="r1", workflow_name="w", workflow_version="1.0.0", state=RunState.RUNNING)
    workflow = Workflow(
        name="w", version="1.0.0", schema_version="v1", description="test", steps=[]
    )
    context = ExecutionContext(session=db_session, run=run)
    skills = {"alpha": {"1.0.0": GENERATIVE_SKILL}, "transcribe": {"1.0.0": TRANSCRIBE}}
    return SteppingTarget(runs_dir, run, context, [], workflow, skills)


def test_a_generative_step_publishes_its_declared_ceiling(
    tmp_path: Path, db_session: Session
) -> None:
    target = _target(tmp_path, db_session)
    step = Step(id="first", skill="alpha", skill_version="1.0.0")

    announce(target, total=1, position=0, step=step)

    state = read_progress(tmp_path, "r1")
    assert state is not None
    assert state.ceiling_seconds == get_settings().provider_timeout_seconds


def test_an_extractive_step_publishes_no_ceiling(tmp_path: Path, db_session: Session) -> None:
    target = _target(tmp_path, db_session)
    step = Step(id="first", skill="transcribe", skill_version="1.0.0")

    announce(target, total=1, position=0, step=step)

    state = read_progress(tmp_path, "r1")
    assert state is not None
    assert state.ceiling_seconds is None


def test_a_step_naming_an_unknown_skill_publishes_no_ceiling(
    tmp_path: Path, db_session: Session
) -> None:
    """UnknownSkillError surfaces loudly elsewhere, once the run reaches the
    step (engine.preparation). announce must not raise it first.
    """
    target = _target(tmp_path, db_session)
    step = Step(id="first", skill="unknown", skill_version="9.9.9")

    announce(target, total=1, position=0, step=step)

    state = read_progress(tmp_path, "r1")
    assert state is not None
    assert state.ceiling_seconds is None
