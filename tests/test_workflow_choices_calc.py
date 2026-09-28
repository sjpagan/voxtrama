"""Unit tests for workflow_choices' arithmetic: hardware_profiles and generative_models.

Split from tests/test_workflow_choices_route.py, which covers the HTTP
surface, so neither file grows past the project's own line limit
(tests/test_architecture_limits.py). Builds Workflow/Step/Skill fixtures
directly, the same way tests/test_engine_choice_check.py does, rather than
loading files: no shipped skill declares anything above
minimum_model_profile 'low', so the boundary case here needs one built by
hand.
"""

from __future__ import annotations

import pytest

from voxtrama.api.routes.workflow_choices import _generative_models, _hardware_profiles
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


def test_hardware_profiles_offers_all_three_when_every_skill_is_low():
    workflow = _workflow([Step(id="a", skill="s", skill_version="1.0.0")])
    skills: SkillRegistry = {"s": {"1.0.0": _skill("s")}}
    assert _hardware_profiles(workflow, skills) == ["low", "base", "high"]


def test_hardware_profiles_drops_low_when_a_built_skill_declares_a_higher_minimum():
    workflow = _workflow([Step(id="a", skill="s", skill_version="1.0.0")])
    skills: SkillRegistry = {"s": {"1.0.0": _skill("s", minimum_model_profile=ModelProfile.BASE)}}
    assert _hardware_profiles(workflow, skills) == ["base", "high"]


def test_generative_models_is_none_when_no_step_declares_models():
    workflow = _workflow([Step(id="a", skill="s", skill_version="1.0.0")])
    assert _generative_models(workflow) is None


def test_generative_models_is_empty_list_when_the_intersection_is_empty():
    steps = [
        Step(id="a", skill="s", skill_version="1.0.0", allows=StepAllows(models=["m1"])),
        Step(id="b", skill="s", skill_version="1.0.0", allows=StepAllows(models=["m2"])),
    ]
    assert _generative_models(_workflow(steps)) == []


def test_hardware_profiles_agrees_with_check_choices_on_every_profile():
    """The test that must never fail silently: a profile this route offers
    is always one check_choices accepts, and one it withholds is always
    one check_choices rejects: same registry, same workflow, both sides.
    """
    workflow = _workflow([Step(id="a", skill="s", skill_version="1.0.0")])
    skills: SkillRegistry = {"s": {"1.0.0": _skill("s", minimum_model_profile=ModelProfile.BASE)}}
    offered = _hardware_profiles(workflow, skills)
    for profile in ["low", "base", "high"]:
        choices = RunChoices(hardware_profile=profile)
        if profile in offered:
            check_choices(choices, workflow, skills)
        else:
            with pytest.raises(ChoicesRejected):
                check_choices(choices, workflow, skills)
