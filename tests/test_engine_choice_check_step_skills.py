"""Unit tests for engine.choice_check: step_skills, and all three rules at once.

Split out of tests/test_engine_choice_check.py, which covers hardware_profile
and generative_model, so neither file grows past the project's line limit
(tests/test_architecture_limits.py).
"""

from __future__ import annotations

import pytest

from voxtrama.engine.choice_check import check_choices
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import SkillRef, Step, StepAllows, Workflow
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


def test_step_skills_on_an_unknown_step_id_is_rejected():
    workflow = _workflow([Step(id="a", skill="summarize", skill_version="1.0.0")])
    skills: SkillRegistry = {"summarize": {"1.0.0": _skill("summarize")}}
    choices = RunChoices(step_skills={"ghost": SkillRef(skill="other", skill_version="1.0.0")})
    with pytest.raises(ChoicesRejected):
        check_choices(choices, workflow, skills)


def test_step_skills_on_a_step_with_a_declared_alternative_is_accepted():
    step = Step(
        id="a",
        skill="summarize",
        skill_version="1.0.0",
        allows=StepAllows(skills=[SkillRef(skill="alt", skill_version="1.0.0")]),
    )
    skills: SkillRegistry = {"summarize": {"1.0.0": _skill("summarize")}}
    choices = RunChoices(step_skills={"a": SkillRef(skill="alt", skill_version="1.0.0")})
    check_choices(choices, _workflow([step]), skills)


def test_step_skills_with_no_alternatives_and_an_unallowed_alternative_reject_differently():
    """The two step_skills failure modes must not read the same.

    A step declaring no alternatives at all is a different fact from a
    step declaring some, none of which match what the run chose. The
    messages must say which one is true.
    """
    skills: SkillRegistry = {"summarize": {"1.0.0": _skill("summarize")}}
    chosen = SkillRef(skill="other", skill_version="1.0.0")

    no_alternatives = _workflow([Step(id="a", skill="summarize", skill_version="1.0.0")])
    with pytest.raises(ChoicesRejected) as exc_none:
        check_choices(RunChoices(step_skills={"a": chosen}), no_alternatives, skills)

    with_alternatives = _workflow(
        [
            Step(
                id="a",
                skill="summarize",
                skill_version="1.0.0",
                allows=StepAllows(skills=[SkillRef(skill="allowed", skill_version="1.0.0")]),
            )
        ]
    )
    with pytest.raises(ChoicesRejected) as exc_wrong:
        check_choices(RunChoices(step_skills={"a": chosen}), with_alternatives, skills)

    assert str(exc_none.value) != str(exc_wrong.value)
    assert "no skill alternatives" in str(exc_none.value)
    assert "no skill alternatives" not in str(exc_wrong.value)


def test_three_violations_together_raise_one_exception_with_three_rejections_in_order():
    step_a = Step(id="a", skill="summarize", skill_version="1.0.0")
    step_b = Step(
        id="b", skill="extract", skill_version="1.0.0", allows=StepAllows(models=["model-x"])
    )
    workflow = _workflow([step_a, step_b])
    skills: SkillRegistry = {
        "summarize": {"1.0.0": _skill("summarize", minimum_model_profile=ModelProfile.HIGH)},
        "extract": {"1.0.0": _skill("extract")},
    }
    choices = RunChoices(
        hardware_profile="low",
        generative_model="model-y",
        step_skills={"ghost": SkillRef(skill="x", skill_version="1.0.0")},
    )
    with pytest.raises(ChoicesRejected) as first:
        check_choices(choices, workflow, skills)
    with pytest.raises(ChoicesRejected) as second:
        check_choices(choices, workflow, skills)

    assert len(first.value.rejections) == 3
    assert first.value.rejections == second.value.rejections
    assert [r.field for r in first.value.rejections] == [
        "hardware_profile",
        "generative_model",
        "step_skills[ghost]",
    ]
