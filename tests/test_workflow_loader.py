"""Validates the loader against the three committed workflows and four negative cases.

The three committed files under workflows/ must load and validate without
requiring any field outside the Workflow schema. The negative cases prove the validator rejects a
malformed workflow before it reaches an engine.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.errors import (
    CyclicDependencyError,
    SkillNotFoundError,
    UnknownStepError,
)
from voxtrama.workflow.loader import SkillRegistry, load_workflow, validate_workflow
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / "workflows"

# Every skill name+version referenced by the three shipped workflows.
# No skill is implemented here; this registry only proves
# the loader can tell a declared skill from a missing one.
_SKILL_NAMES = [
    "transcribe",
    "diarize",
    # This held the whole original chain, including skills nobody ever wrote
    # (detect_pii, human_review, export), and summarize was missing: the
    # only generative skill the engine registers, and one no workflow
    # named. A fake registry richer than the real one protects nothing:
    # it is what let an unreachable summary through.
    "summarize",
    "detect_pii",
    "extract_decisions",
    "validate_evidence",
    "human_review",
    "export",
    "build_index",
    "extract_concepts",
    "generate_review_questions",
    "extract_themes",
    "extract_quotes",
]


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


@pytest.fixture
def registry() -> SkillRegistry:
    return {name: {"1.0.0": _skill(name)} for name in _SKILL_NAMES}


@pytest.mark.parametrize(
    "filename",
    ["meeting-decisions.yaml", "lesson-companion.yaml", "research-interview.yaml"],
)
def test_the_three_par_7_workflows_load_and_validate(filename: str, registry: SkillRegistry):
    workflow = load_workflow(WORKFLOWS_DIR / filename, registry)
    assert isinstance(workflow, Workflow)
    assert workflow.steps


def test_a_field_outside_the_schema_is_rejected_with_its_path():
    raw = {
        "name": "bad",
        "version": "1.0.0",
        "schema_version": "v1",
        "description": "has an extra field",
        "steps": [{"id": "transcribe", "skill": "transcribe", "skill_version": "1.0.0"}],
        "not_a_real_field": True,
    }
    with pytest.raises(ValidationError, match="not_a_real_field"):
        Workflow.model_validate(raw)


def test_a_circular_dependency_between_two_steps_is_rejected(registry: SkillRegistry):
    workflow = Workflow.model_validate(
        {
            "name": "cyclic",
            "version": "1.0.0",
            "schema_version": "v1",
            "description": "a depends on b, b depends on a",
            "steps": [
                {"id": "a", "skill": "transcribe", "skill_version": "1.0.0", "depends_on": ["b"]},
                {"id": "b", "skill": "diarize", "skill_version": "1.0.0", "depends_on": ["a"]},
            ],
        }
    )
    with pytest.raises(CyclicDependencyError, match="a -> b -> a"):
        validate_workflow(workflow, registry)


def test_a_step_citing_a_nonexistent_skill_is_rejected(registry: SkillRegistry):
    workflow = Workflow.model_validate(
        {
            "name": "missing-skill",
            "version": "1.0.0",
            "schema_version": "v1",
            "description": "cites a skill that was never declared",
            "steps": [{"id": "a", "skill": "does_not_exist", "skill_version": "1.0.0"}],
        }
    )
    with pytest.raises(SkillNotFoundError, match=r"steps\[0\]\.skill"):
        validate_workflow(workflow, registry)


def test_a_dependency_on_a_nonexistent_step_is_rejected(registry: SkillRegistry):
    workflow = Workflow.model_validate(
        {
            "name": "missing-step",
            "version": "1.0.0",
            "schema_version": "v1",
            "description": "depends_on names a step that is not there",
            "steps": [
                {
                    "id": "a",
                    "skill": "transcribe",
                    "skill_version": "1.0.0",
                    "depends_on": ["ghost"],
                }
            ],
        }
    )
    with pytest.raises(UnknownStepError, match=r"steps\[0\]\.depends_on"):
        validate_workflow(workflow, registry)
