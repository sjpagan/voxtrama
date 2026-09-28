"""SkillFile: the format of a generative skill written as a file.

Loading is what tests/test_engine_skill_catalog.py exercises end to end.
This file only checks that a bad file is rejected, and rejected saying why.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from voxtrama.workflow.skill_file import SkillFileError, load_skill_file

_VALID_SKILL: dict[str, object] = {
    "name": "greet",
    "version": "1.0.0",
    "input_schema": {"type": "object"},
    "output_schema": {"type": "object"},
    "model_class": "generative",
    "minimum_model_profile": "low",
    "evidence_required": False,
    "minimum_confidence": 0.0,
    "review_required": False,
    "retention_policy": "follows_recording",
    "privacy": "any",
}


def _write(tmp_path: Path, skill: dict[str, object], prompt: str = "Hello, {language}.") -> Path:
    path = tmp_path / "skill.yaml"
    path.write_text(yaml.safe_dump({"skill": skill, "prompt": prompt}))
    return path


def test_a_valid_generative_skill_file_loads(tmp_path: Path) -> None:
    skill_file = load_skill_file(_write(tmp_path, _VALID_SKILL))

    assert skill_file.skill.name == "greet"
    assert skill_file.prompt == "Hello, {language}."


def test_an_extractive_skill_file_is_rejected_saying_why(tmp_path: Path) -> None:
    extractive = {**_VALID_SKILL, "model_class": "extractive"}
    path = _write(tmp_path, extractive)

    with pytest.raises(SkillFileError, match="model_class") as excinfo:
        load_skill_file(path)
    assert str(path) in str(excinfo.value)


def test_a_missing_field_is_rejected_naming_the_field(tmp_path: Path) -> None:
    incomplete = {k: v for k, v in _VALID_SKILL.items() if k != "retention_policy"}
    path = _write(tmp_path, incomplete)

    with pytest.raises(SkillFileError, match="retention_policy") as excinfo:
        load_skill_file(path)
    assert str(path) in str(excinfo.value)


def test_an_out_of_range_field_is_rejected_naming_the_field(tmp_path: Path) -> None:
    malformed = {**_VALID_SKILL, "minimum_confidence": 1.5}
    path = _write(tmp_path, malformed)

    with pytest.raises(SkillFileError, match="minimum_confidence"):
        load_skill_file(path)


def test_a_workflow_only_field_is_rejected(tmp_path: Path) -> None:
    """depends_on, condition, on_error are the workflow's, never a skill's."""
    path = tmp_path / "skill.yaml"
    path.write_text(
        yaml.safe_dump({"skill": _VALID_SKILL, "prompt": "Hello.", "depends_on": ["transcribe"]})
    )

    with pytest.raises(SkillFileError, match="depends_on"):
        load_skill_file(path)
