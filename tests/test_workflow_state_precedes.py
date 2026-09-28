"""A steps.<id>.state condition only means something once depends_on says so.

Split from test_workflow_condition_loader.py to stay under its line limit:
that file is about a condition's own grammar (literal, operator, the
output_schema collision). This is about the depends_on graph around it:
engine.steps.resolve_order orders purely on depends_on and never looks at
condition, so a state condition on a step that is not a depends_on ancestor
would read `pending` at run time instead of the state it names.
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


def test_a_state_condition_on_a_step_that_is_not_an_ancestor_is_rejected_by_the_loader() -> None:
    workflow = Workflow.model_validate(
        {
            "name": "state-not-an-ancestor",
            "version": "1.0.0",
            "schema_version": "v1",
            "description": "a's condition reads b's state, but a does not depend on b",
            "steps": [
                {
                    "id": "a",
                    "skill": "transcribe",
                    "skill_version": "1.0.0",
                    "condition": 'steps.b.state == "succeeded"',
                },
                {"id": "b", "skill": "transcribe", "skill_version": "1.0.0"},
            ],
        }
    )
    with pytest.raises(WorkflowValidationError) as excinfo:
        validate_workflow(workflow, _registry())
    assert "b" in str(excinfo.value)
    assert "depends_on" in str(excinfo.value)


def test_a_state_condition_on_a_transitive_ancestor_loads_fine() -> None:
    """x <- z <- y: y's condition reads x's state without depending on it directly."""
    workflow = Workflow.model_validate(
        {
            "name": "state-transitive-ancestor",
            "version": "1.0.0",
            "schema_version": "v1",
            "description": "y depends on z, z depends on x, y's condition reads x's state",
            "steps": [
                {"id": "x", "skill": "transcribe", "skill_version": "1.0.0"},
                {"id": "z", "skill": "transcribe", "skill_version": "1.0.0", "depends_on": ["x"]},
                {
                    "id": "y",
                    "skill": "transcribe",
                    "skill_version": "1.0.0",
                    "depends_on": ["z"],
                    "condition": 'steps.x.state == "succeeded"',
                },
            ],
        }
    )
    validate_workflow(workflow, _registry())
