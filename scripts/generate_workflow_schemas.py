#!/usr/bin/env python3
"""Regenerate schemas/skill-v1.json, schemas/workflow-v1.json and schemas/tuning-v1.json.

Run this after any change to voxtrama.workflow.skill.Skill,
voxtrama.workflow.definition.Workflow or voxtrama.tuning.definition.TuningFile:
tests/test_schemas_are_current.py fails until the committed files match this
output again.
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


def main() -> None:
    SCHEMAS_DIR.mkdir(exist_ok=True)
    for filename, model in TARGETS.items():
        schema = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        (SCHEMAS_DIR / filename).write_text(schema)


if __name__ == "__main__":
    main()
