"""The loader must resolve `allows.skills`, not just `skill`.

Split out of tests/test_workflow_loader.py, which is already at its own
line limit: an alternative a step declares is a promise the workflow makes
to whatever run picks it, and the promise must be checked at load time,
not discovered mid-run when a run chooses it.
"""

from __future__ import annotations

import pytest

from voxtrama.workflow.definition import SkillRef, Step, StepAllows, Workflow
from voxtrama.workflow.errors import SkillNotFoundError
from voxtrama.workflow.loader import SkillRegistry, validate_workflow
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill


def _skill(name: str) -> Skill:
    return Skill(
        name=name,
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=ModelClass.EXTRACTIVE,
        minimum_model_profile=ModelProfile.BASE,
        evidence_required=True,
        minimum_confidence=0.5,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )


def _workflow(allows: StepAllows) -> Workflow:
    step = Step(id="a", skill="transcribe", skill_version="1.0.0", allows=allows)
    return Workflow(
        name="wf", version="1.0.0", schema_version="v1", description="test fixture", steps=[step]
    )


def test_an_unknown_alternative_in_allows_skills_is_rejected_with_its_field_path():
    registry: SkillRegistry = {"transcribe": {"1.0.0": _skill("transcribe")}}
    allows = StepAllows(skills=[SkillRef(skill="does_not_exist", skill_version="9.9.9")])
    with pytest.raises(SkillNotFoundError, match=r"steps\[0\]\.allows\.skills\[0\]"):
        validate_workflow(_workflow(allows), registry)


def test_a_known_alternative_in_allows_skills_loads():
    registry: SkillRegistry = {
        "transcribe": {"1.0.0": _skill("transcribe")},
        "other": {"1.0.0": _skill("other")},
    }
    allows = StepAllows(skills=[SkillRef(skill="other", skill_version="1.0.0")])
    validate_workflow(_workflow(allows), registry)
