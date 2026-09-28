"""Reading a domain document fails the same way regardless of which one it is.

Covers the three ways a workflow or a skill file can fail to load
(unreadable, malformed YAML, an invalid field), each naming the file.
The malformed-YAML case for a workflow is the defect once fixed only for
skill files: load_workflow used to let yaml's own parser error through
unnamed. The schema itself is exercised elsewhere (test_workflow_loader.py,
test_workflow_skill_file.py). This only checks what a read failure says.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from voxtrama.workflow.errors import WorkflowValidationError
from voxtrama.workflow.loader import load_workflow
from voxtrama.workflow.skill_file import SkillFileError, load_skill_file

_WORKFLOW_WITH_EXTRA_FIELD: dict[str, object] = {
    "name": "bad",
    "version": "1.0.0",
    "schema_version": "v1",
    "description": "an otherwise valid workflow with an extra field",
    "steps": [],
    "not_a_real_field": True,
}


def test_an_unreadable_workflow_file_names_the_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(WorkflowValidationError) as excinfo:
        load_workflow(missing, {})
    assert str(missing) in str(excinfo.value)


def test_a_malformed_workflow_yaml_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("name: [this is not valid yaml\n")
    with pytest.raises(WorkflowValidationError) as excinfo:
        load_workflow(path, {})
    assert str(path) in str(excinfo.value)


def test_a_workflow_with_an_invalid_field_names_file_and_field(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(_WORKFLOW_WITH_EXTRA_FIELD))
    with pytest.raises(WorkflowValidationError) as excinfo:
        load_workflow(path, {})
    assert str(path) in str(excinfo.value)
    assert "not_a_real_field" in str(excinfo.value)


def test_an_unreadable_skill_file_names_the_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(SkillFileError) as excinfo:
        load_skill_file(missing)
    assert str(missing) in str(excinfo.value)


def test_a_malformed_skill_yaml_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("skill: [this is not valid yaml\n")
    with pytest.raises(SkillFileError) as excinfo:
        load_skill_file(path)
    assert str(path) in str(excinfo.value)


# A skill file with an invalid field naming both file and field is already
# covered by test_workflow_skill_file.py::test_a_missing_field_is_rejected_
# naming_the_field, which asserts both the field name and str(path), so it is
# not duplicated here.
