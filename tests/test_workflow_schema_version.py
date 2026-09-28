"""A workflow file for a shape this version does not read is refused.

Until 1.0 Voxtrama promises nothing about compatibility between versions:
it reads `schema_version: v1` and nothing else. Before this, the field was
a free string and `v2` loaded without a word, as if it were understood.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxtrama.workflow.errors import SkillNotFoundError, WorkflowValidationError
from voxtrama.workflow.loader import load_workflow

_WORKFLOW = """\
name: w
version: 1.0.0
schema_version: {version}
description: A one-step workflow.
steps:
  - id: transcribe
    skill: transcribe
    skill_version: 1.0.0
"""


@pytest.mark.parametrize("version", ["v2", "v0", "1", "'v1 '"])
def test_a_shape_other_than_v1_is_refused_naming_the_one_accepted(
    tmp_path: Path, version: str
) -> None:
    path = tmp_path / "w.yaml"
    path.write_text(_WORKFLOW.format(version=version))

    with pytest.raises(WorkflowValidationError, match=r"schema_version.*'v1'"):
        load_workflow(path, {})


def test_v1_still_loads(tmp_path: Path) -> None:
    path = tmp_path / "w.yaml"
    path.write_text(_WORKFLOW.format(version="v1"))

    # The shape is accepted: what fails next is the empty skill registry.
    with pytest.raises(SkillNotFoundError):
        load_workflow(path, {})
