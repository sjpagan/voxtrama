"""StepAllows replaces model_override: the loader must know both facts.

A workflow file written against the old, opaque model_override field must
now be rejected (extra="forbid" makes that automatic), and the real
meeting-decisions.yaml must still load, now declaring the allows it was
given for extract_decisions.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from voxtrama.engine.catalog import load_named_workflow
from voxtrama.workflow.definition import SkillRef, Workflow


def test_a_step_with_the_removed_model_override_field_is_rejected():
    raw = {
        "name": "old-style",
        "version": "1.0.0",
        "schema_version": "v1",
        "description": "written before model_override was removed",
        "steps": [
            {
                "id": "a",
                "skill": "transcribe",
                "skill_version": "1.0.0",
                "model_override": {"model": "something"},
            }
        ],
    }
    with pytest.raises(ValidationError, match="model_override"):
        Workflow.model_validate(raw)


def test_meeting_decisions_still_loads_and_declares_extract_decisions_allows():
    workflow = load_named_workflow("meeting-decisions")
    step = next(s for s in workflow.steps if s.id == "extract_decisions")
    assert step.allows.skills == [SkillRef(skill="extract_themes", skill_version="1.0.0")]
    assert step.allows.models == ["qwen2.5:0.5b", "qwen3:30b"]
