"""Guards schemas/*.json against drifting from the Pydantic models that define them.

The JSON Schema files are generated, not hand-written: this
test fails the moment a model changes and nobody re-ran
scripts/generate_workflow_schemas.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from voxtrama.tuning.definition import TuningFile
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.skill import Skill

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"

TARGETS = {
    "skill-v1.json": Skill,
    "workflow-v1.json": Workflow,
    "tuning-v1.json": TuningFile,
}


def _rendered(model: type) -> str:
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def test_committed_schemas_match_the_pydantic_models():
    stale = [
        filename
        for filename, model in TARGETS.items()
        if (SCHEMAS_DIR / filename).read_text() != _rendered(model)
    ]
    assert not stale, (
        f"stale schema files, regenerate with scripts/generate_workflow_schemas.py: {stale}"
    )
