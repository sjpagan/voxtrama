"""A skill chosen among a step's declared alternatives really executes:
RunStep and the manifest report the chosen skill, not the workflow's own
default.

check_choices' own rules are covered by test_engine_choice_check.py and
test_engine_choice_check_step_skills.py. This file drives the substitution
through execute_run, the way engine.preparation._apply_step_choices applies
it, and reads both the RunStep row and the manifest back.

The case where the workflow changes underneath a queued run, and
prepare_run's own re-check of choices, lives in
test_engine_run_choices_recheck.py, split out so neither file grows past
the project's size limit.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.step import RunStep
from voxtrama.engine import run as engine_run
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
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


def _workflow() -> Workflow:
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


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def test_the_chosen_alternative_skill_is_what_actually_runs(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    choices = RunChoices(
        step_skills={"summarize": SkillRef(skill="alt-skill", skill_version="1.0.0")}
    )
    created = create_run(db_session, "choice-workflow", "unpinned", choices=choices)

    run = execute_run(db_session, created.id, workflow=_workflow())

    row = db_session.scalars(select(RunStep).where(RunStep.run_id == run.id)).one()
    assert (row.skill, row.skill_version) == ("alt-skill", "1.0.0")

    manifest = _read_manifest(run.id)
    assert manifest.steps[0].skill == "alt-skill"
    assert manifest.choices.step_skills == {"summarize": "alt-skill@1.0.0"}
