"""prepare_run re-checks a run's choices against the workflow it resolves,
rather than trusting what engine.enqueue.enqueue_run already accepted.

A user's own copy of a workflow file can be edited at any time,
including while a Run sits queued between acceptance and execution. A
choice that was allowed then can stop being allowed by the time a worker
gets to it. execute_run's `workflow` parameter is the injection point its
own docstring already offers tests, used here to stand in for "the file
changed underneath the queued run".

Split out of test_engine_run_choices.py, which covers the substitution
itself, to keep both files under the project's size limit.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.engine import run as engine_run
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.queue.job import JobState
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import SkillRef, Step, StepAllows, Workflow
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill


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


def _workflow_with_alternative() -> Workflow:
    step = Step(
        id="summarize",
        skill="default-skill",
        skill_version="1.0.0",
        allows=StepAllows(skills=[SkillRef(skill="alt-skill", skill_version="1.0.0")]),
    )
    return Workflow(
        name="choice-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow whose one step declares an alternative skill.",
        steps=[step],
    )


def _workflow_without_alternative() -> Workflow:
    """Same step id, edited to no longer offer the alternative."""
    step = Step(id="summarize", skill="default-skill", skill_version="1.0.0")
    return Workflow(
        name="choice-workflow",
        version="1.0.1",
        schema_version="v1",
        description="The workflow, edited to no longer offer the alternative.",
        steps=[step],
    )


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def _choices() -> RunChoices:
    return RunChoices(step_skills={"summarize": SkillRef(skill="alt-skill", skill_version="1.0.0")})


def test_a_choice_the_workflow_no_longer_allows_fails_the_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The choice was allowed by the workflow engine.enqueue.enqueue_run saw
    when the request was accepted. The workflow execute_run resolves here
    (the way a worker does, by name, from the catalogue) no longer offers
    it. prepare_run's own re-check must fail the run, not apply a
    substitution the current workflow no longer permits.
    """
    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"default-skill": lambda ctx: {}})
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {"default-skill": {"1.0.0": _skill("default-skill")}}
    )
    created = create_run(db_session, "choice-workflow", "unpinned", choices=_choices())

    run = execute_run(db_session, created.id, workflow=_workflow_without_alternative())

    assert run.state == JobState.FAILED
    assert run.error_code == "choices_rejected"
    assert "summarize" in (run.error or "")


def test_the_same_choice_executes_normally_when_the_workflow_is_unchanged(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards the test above: without this, it would pass even if
    prepare_run rejected every choice unconditionally.
    """
    monkeypatch.setattr(
        engine_run,
        "BUILTIN_STEPS",
        {"default-skill": lambda ctx: {}, "alt-skill": lambda ctx: {}},
    )
    monkeypatch.setattr(
        engine_run,
        "BUILTIN_SKILLS",
        {
            "default-skill": {"1.0.0": _skill("default-skill")},
            "alt-skill": {"1.0.0": _skill("alt-skill")},
        },
    )
    created = create_run(db_session, "choice-workflow", "unpinned", choices=_choices())

    run = execute_run(db_session, created.id, workflow=_workflow_with_alternative())

    assert run.state == JobState.SUCCEEDED


def test_the_failed_runs_manifest_reports_the_choices_rejected_code(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"default-skill": lambda ctx: {}})
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {"default-skill": {"1.0.0": _skill("default-skill")}}
    )
    created = create_run(db_session, "choice-workflow", "unpinned", choices=_choices())

    run = execute_run(db_session, created.id, workflow=_workflow_without_alternative())

    manifest = _read_manifest(run.id)
    assert manifest.failure is not None
    assert manifest.failure.code == "choices_rejected"
