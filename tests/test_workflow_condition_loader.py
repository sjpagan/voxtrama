"""A malformed condition is a loading-time error, not a runtime one.

Split from test_workflow_loader.py to stay under its line threshold: that
file's negative cases are about the shape of a step, this one is about
what a step's `condition` may say (workflow.condition's own grammar).
"""

from __future__ import annotations

import pytest

from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.errors import WorkflowValidationError
from voxtrama.workflow.loader import SkillRegistry, validate_workflow
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill


def _registry() -> SkillRegistry:
    skill = Skill(
        name="transcribe",
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
    return {"transcribe": {"1.0.0": skill}}


def _registry_with_state_output() -> SkillRegistry:
    """A skill whose own output collides with steps.<id>.state."""
    skill = Skill(
        name="extract",
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object", "properties": {"state": {"type": "string"}}},
        model_class=ModelClass.EXTRACTIVE,
        minimum_model_profile=ModelProfile.BASE,
        evidence_required=True,
        minimum_confidence=0.5,
        review_required=False,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )
    registry = _registry()
    registry["extract"] = {"1.0.0": skill}
    return registry


def _two_step_workflow(condition: str, target_skill: str = "transcribe") -> Workflow:
    return Workflow.model_validate(
        {
            "name": "state-condition",
            "version": "1.0.0",
            "schema_version": "v1",
            "description": "a's condition reads b's state",
            "steps": [
                {
                    "id": "a",
                    "skill": "transcribe",
                    "skill_version": "1.0.0",
                    "condition": condition,
                },
                {"id": "b", "skill": target_skill, "skill_version": "1.0.0"},
            ],
        }
    )


def test_a_state_literal_outside_the_three_values_is_rejected_by_the_loader() -> None:
    workflow = _two_step_workflow('steps.b.state == "riuscito"')
    with pytest.raises(WorkflowValidationError) as excinfo:
        validate_workflow(workflow, _registry())
    for value in ("succeeded", "failed", "skipped"):
        assert value in str(excinfo.value)


def test_an_ordering_operator_on_state_is_rejected_by_the_loader() -> None:
    workflow = _two_step_workflow('steps.b.state > "failed"')
    with pytest.raises(WorkflowValidationError, match="operator"):
        validate_workflow(workflow, _registry())


def test_a_condition_on_state_colliding_with_the_skill_s_own_output_is_rejected() -> None:
    workflow = _two_step_workflow('steps.b.state == "succeeded"', target_skill="extract")
    with pytest.raises(WorkflowValidationError, match="extract"):
        validate_workflow(workflow, _registry_with_state_output())


def test_a_skill_declaring_state_without_a_condition_reading_it_loads_fine() -> None:
    """The collision is only real when a condition reads it."""
    workflow = Workflow.model_validate(
        {
            "name": "state-no-collision",
            "version": "1.0.0",
            "schema_version": "v1",
            "description": "the skill's own 'state' is harmless without a matching condition",
            "steps": [{"id": "b", "skill": "extract", "skill_version": "1.0.0"}],
        }
    )
    validate_workflow(workflow, _registry_with_state_output())


def test_a_malformed_condition_is_rejected_by_the_loader() -> None:
    workflow = Workflow.model_validate(
        {
            "name": "bad-condition",
            "version": "1.0.0",
            "schema_version": "v1",
            "description": "condition names a path outside the allowed list",
            "steps": [
                {
                    "id": "a",
                    "skill": "transcribe",
                    "skill_version": "1.0.0",
                    "condition": "recording.nonsense > 1",
                }
            ],
        }
    )
    with pytest.raises(WorkflowValidationError, match=r"steps\[0\]\.condition"):
        validate_workflow(workflow, _registry())
