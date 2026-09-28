"""output.json as engine.run writes it, on a run that fails.

Split from test_engine_output.py, which covers the same file on a
successful run: the same split as test_engine_manifest.py would need if it
grew past the test suite's own size limit. write_run_output and
read_run_output are unit-tested on their own in test_manifest_output.py.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.output import output_path, read_run_output
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


def _skill(name: str) -> Skill:
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


def _install(monkeypatch: pytest.MonkeyPatch, steps: dict) -> None:
    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", steps)
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {name: {"1.0.0": _skill(name)} for name in steps}
    )


def _runs_dir():
    return get_paths(get_settings().data_dir).runs_dir


def test_a_failed_runs_output_carries_the_steps_that_already_passed(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(ctx: ExecutionContext) -> dict:
        raise RuntimeError("step exploded")

    _install(monkeypatch, {"first": lambda ctx: {"value": "done"}, "second": _boom})
    created = create_run(db_session, "test-workflow", "unpinned")
    workflow = _workflow(
        Step(id="first", skill="first", skill_version="1.0.0"),
        Step(id="second", skill="second", skill_version="1.0.0", depends_on=["first"]),
    )

    run = execute_run(db_session, created.id, workflow=workflow)

    assert run.state == JobState.FAILED
    payload = json.loads(output_path(_runs_dir(), run.id).read_bytes())
    assert payload["steps"] == {"first": {"value": "done"}}


def test_a_run_that_fails_before_planning_still_writes_an_empty_output(
    db_session: Session,
) -> None:
    """No workflow named "no-such-workflow" exists: prepare_run raises before
    a single step is planned, and fail_run is called with no context at all.
    """
    created = create_run(db_session, "no-such-workflow", "unpinned")

    run = execute_run(db_session, created.id)

    assert run.state == JobState.FAILED
    output = read_run_output(_runs_dir(), run.id)
    assert output is not None
    assert output.steps == {}
