"""Unit tests for the Skill and Workflow models themselves.

Loading real workflow files against a skill registry is covered by
tests/test_workflow_loader.py. This file only checks the shape.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from voxtrama.workflow.definition import OnError, Step, Workflow
from voxtrama.workflow.skill import (
    SAME_AS_AUDIO,
    Determinism,
    ModelClass,
    ModelProfile,
    Privacy,
    Skill,
)


def _skill_kwargs(**overrides: object) -> dict[str, object]:
    base = dict(
        name="extract_decisions",
        version="1.0.0",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        model_class=ModelClass.EXTRACTIVE,
        minimum_model_profile=ModelProfile.BASE,
        evidence_required=True,
        minimum_confidence=0.8,
        review_required=True,
        retention_policy="follows_recording",
        privacy=Privacy.LOCAL_ONLY,
    )
    base.update(overrides)
    return base


def test_extractive_skill_is_deterministic_same_host():
    skill = Skill(**_skill_kwargs(model_class=ModelClass.EXTRACTIVE))
    assert skill.deterministic == Determinism.SAME_HOST


def test_generative_skill_is_non_deterministic():
    skill = Skill(**_skill_kwargs(model_class=ModelClass.GENERATIVE))
    assert skill.deterministic == Determinism.NON_DETERMINISTIC


def test_deterministic_is_not_a_settable_field():
    with pytest.raises(ValidationError):
        Skill(**_skill_kwargs(deterministic="deterministic"))


def test_output_language_defaults_to_same_as_audio():
    skill = Skill(**_skill_kwargs())
    assert skill.output_language == SAME_AS_AUDIO


def test_minimum_confidence_out_of_range_is_rejected():
    with pytest.raises(ValidationError):
        Skill(**_skill_kwargs(minimum_confidence=1.5))


def test_unknown_skill_field_is_rejected():
    with pytest.raises(ValidationError):
        Skill(**_skill_kwargs(extra_field="nope"))


def test_workflow_with_a_single_step_is_valid():
    workflow = Workflow(
        name="minimal",
        version="1.0.0",
        schema_version="v1",
        description="A single-step workflow.",
        steps=[Step(id="transcribe", skill="transcribe", skill_version="1.0.0")],
    )
    assert workflow.steps[0].on_error == OnError()
