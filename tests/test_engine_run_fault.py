"""Tests that an engine fault during execute_run always closes the run.

Split from test_engine_run.py: that file covers a *step's own* failure,
already handled elsewhere (run_with_fallback returns it as a
value). This one covers the engine itself faulting: inside the per-step
loop, where a step can be named, and outside it, where none can.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.failure import fail_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow


def _workflow(*steps: Step) -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=list(steps),
    )


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def _bad_condition_workflow() -> Workflow:
    # A condition on a step, referencing that same step: engine.condition
    # raises ConditionEvaluationError because nothing has produced anything
    # yet when the condition is checked, before the step runs. The workflow loader
    # would reject this at load time. The engine gets it anyway when a
    # Workflow is built by hand, as here.
    step = Step(id="only", skill="whatever", skill_version="1.0.0", condition="steps.only.x == 1")
    return _workflow(step)


def test_a_fault_inside_the_loop_closes_the_run_and_names_the_step(db_session: Session) -> None:
    created = create_run(db_session, "test-workflow", "unpinned")

    run = execute_run(db_session, created.id, workflow=_bad_condition_workflow())

    assert run.state == JobState.FAILED
    assert run.error_code == "internal"
    assert run.error_step == "only"
    assert "steps.only" in (run.error or "")


def test_a_fault_inside_the_loop_writes_a_final_manifest(db_session: Session) -> None:
    created = create_run(db_session, "test-workflow", "unpinned")

    run = execute_run(db_session, created.id, workflow=_bad_condition_workflow())

    manifest = _read_manifest(run.id)
    assert manifest.run.final is True
    assert manifest.failure is not None
    assert manifest.failure.code == "internal"


def test_a_fault_outside_the_loop_closes_the_run_with_no_step_named(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(target: object) -> None:
        raise RuntimeError("manifest disk full")

    # Patched on engine.run's own name for it, not engine.stepping's: that
    # is what makes this the *initial* publish, before the loop. The one
    # step_loop.run_steps calls keeps its own, untouched, reference.
    monkeypatch.setattr(engine_run, "publish_manifest", _boom)
    created = create_run(db_session, "test-workflow", "unpinned")

    run = execute_run(db_session, created.id, workflow=_bad_condition_workflow())

    assert run.state == JobState.FAILED
    assert run.error_step is None


def test_a_fault_after_success_does_not_reopen_the_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def _boom_on_the_final_call(target: object) -> None:
        calls["n"] += 1
        if calls["n"] < 2:
            return
        raise RuntimeError("manifest disk full")

    # Same substitution as above, but this one only fails on the *second*
    # publish_manifest call, the one after run.state is already SUCCEEDED
    # and committed. Without the guard in fail_run, this is the
    # regression: a run that finished well gets overwritten as failed.
    monkeypatch.setattr(engine_run, "publish_manifest", _boom_on_the_final_call)
    created = create_run(db_session, "test-workflow", "unpinned")

    run = execute_run(db_session, created.id, workflow=_workflow())

    assert run.state == JobState.SUCCEEDED
    assert run.error_code is None


def test_fail_run_does_not_touch_a_run_already_succeeded(db_session: Session) -> None:
    created = create_run(db_session, "test-workflow", "unpinned")
    run = execute_run(db_session, created.id, workflow=_workflow())
    assert run.state == JobState.SUCCEEDED

    result = fail_run(db_session, run, RuntimeError("should not apply"))

    assert result.state == JobState.SUCCEEDED
    assert result.error is None
    assert result.error_code is None


def test_a_keyboard_interrupt_inside_the_loop_is_not_reported_as_a_failed_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _ctrl_c(ctx: ExecutionContext) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"alpha": _ctrl_c})
    created = create_run(db_session, "test-workflow", "unpinned")
    workflow = _workflow(Step(id="only", skill="alpha", skill_version="1.0.0"))

    # Deliberately not caught anywhere: a Ctrl-C is someone asking the run
    # to stop, not the work failing, and turning it into a "failed" run
    # would misreport who stopped it. That is the reconciler's job
    # (engine.reconcile), not this one's.
    with pytest.raises(KeyboardInterrupt):
        execute_run(db_session, created.id, workflow=workflow)

    db_session.refresh(created)
    assert created.state == JobState.RUNNING
