"""Unit tests for engine.choice_check: hardware_profile and generative_model.

step_skills and the "three violations at once" case live in
tests/test_engine_choice_check_step_skills.py, kept separate so neither
file grows past the project's own line limit (tests/test_architecture_limits.py).
Builds small Workflow/Skill fixtures directly rather than loading files.
tests/test_workflow_step_allows.py covers the same rule exercised against
the real meeting-decisions.yaml.
"""

from __future__ import annotations

import pytest

from voxtrama.engine.choice_check import check_choices
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step, StepAllows, Workflow
from voxtrama.workflow.loader import SkillRegistry
from voxtrama.workflow.rejection import ChoicesRejected
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill


def _skill(name: str, minimum_model_profile: ModelProfile = ModelProfile.LOW) -> Skill:
    return Skill(
        name=name,
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=ModelClass.EXTRACTIVE,
        minimum_model_profile=minimum_model_profile,
        evidence_required=False,
        minimum_confidence=0.0,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.ANY,
    )


def _workflow(steps: list[Step]) -> Workflow:
    return Workflow(
        name="wf", version="1.0.0", schema_version="v1", description="test fixture", steps=steps
    )


def test_an_empty_run_choices_produces_no_rejections():
    workflow = _workflow([Step(id="a", skill="summarize", skill_version="1.0.0")])
    skills: SkillRegistry = {"summarize": {"1.0.0": _skill("summarize")}}
    check_choices(RunChoices(), workflow, skills)


def test_hardware_profile_below_a_skills_minimum_is_rejected_naming_skill_and_field():
    workflow = _workflow([Step(id="a", skill="summarize", skill_version="1.0.0")])
    skills: SkillRegistry = {
        "summarize": {"1.0.0": _skill("summarize", minimum_model_profile=ModelProfile.HIGH)}
    }
    with pytest.raises(ChoicesRejected) as exc:
        check_choices(RunChoices(hardware_profile="low"), workflow, skills)
    message = str(exc.value)
    assert "skill summarize@1.0.0" in message
    assert "minimum_model_profile 'high'" in message
    assert "hardware_profile 'low'" in message


def test_hardware_profile_at_or_above_a_skills_minimum_is_accepted():
    workflow = _workflow([Step(id="a", skill="summarize", skill_version="1.0.0")])
    skills: SkillRegistry = {
        "summarize": {"1.0.0": _skill("summarize", minimum_model_profile=ModelProfile.BASE)}
    }
    check_choices(RunChoices(hardware_profile="high"), workflow, skills)


def test_generative_model_outside_allows_models_is_rejected():
    step = Step(
        id="a",
        skill="summarize",
        skill_version="1.0.0",
        allows=StepAllows(models=["model-a", "model-b"]),
    )
    skills: SkillRegistry = {"summarize": {"1.0.0": _skill("summarize")}}
    with pytest.raises(ChoicesRejected):
        check_choices(RunChoices(generative_model="model-c"), _workflow([step]), skills)


def test_any_generative_model_is_accepted_when_no_step_declares_models():
    workflow = _workflow([Step(id="a", skill="summarize", skill_version="1.0.0")])
    skills: SkillRegistry = {"summarize": {"1.0.0": _skill("summarize")}}
    check_choices(RunChoices(generative_model="anything"), workflow, skills)


def test_check_choices_wires_in_the_diarize_dependency_check():
    """The rule itself lives in tests/test_engine_diarize_choice.py. This only
    proves check_choices calls it.
    """
    workflow = _workflow(
        [
            Step(id="diarize", skill="diarize", skill_version="1.0.0"),
            Step(id="extract", skill="extract", skill_version="1.0.0", depends_on=["diarize"]),
        ]
    )
    skills: SkillRegistry = {
        "diarize": {"1.0.0": _skill("diarize")},
        "extract": {"1.0.0": _skill("extract")},
    }
    with pytest.raises(ChoicesRejected) as exc:
        check_choices(RunChoices(diarize=False), workflow, skills)
    assert "diarize" in str(exc.value)
