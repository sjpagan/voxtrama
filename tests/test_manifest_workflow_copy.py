"""manifest.workflow_copy: the run's own copy of its workflow, written once.

Unit-level, unlike test_engine_superseded_run_copy.py and
test_engine_reconcile_workflow_copy.py, which prove the two engine callers
read this copy back instead of the catalogue. This file only
proves the module itself: what gets written, that it is written once, and
that a missing or corrupt file never raises.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.manifest.workflow_copy import (
    read_workflow_copy,
    workflow_copy_path,
    workflow_definition_payload,
    workflow_definition_sha256,
    write_workflow_copy,
)
from voxtrama.workflow.definition import Step, Workflow


def _workflow(description: str = "A workflow built in a test.") -> Workflow:
    return Workflow(
        name="demo",
        version="1.0.0",
        schema_version="v1",
        description=description,
        steps=[Step(id="t", skill="t", skill_version="1.0.0")],
    )


def test_the_written_copy_reads_back_equal_to_the_original(tmp_path: Path) -> None:
    workflow = _workflow()

    write_workflow_copy(tmp_path, "run-1", workflow)

    assert workflow_copy_path(tmp_path, "run-1").is_file()
    assert read_workflow_copy(tmp_path, "run-1") == workflow


def test_the_copy_matches_the_hash_the_manifest_carries(tmp_path: Path) -> None:
    """The copy and manifest.workflow.definition_sha256
    must describe the same payload, or a reader could never tell the two apart."""
    workflow = _workflow()

    write_workflow_copy(tmp_path, "run-1", workflow)
    reread = read_workflow_copy(tmp_path, "run-1")

    assert reread is not None
    assert workflow_definition_sha256(reread) == workflow_definition_sha256(workflow)


def test_a_second_write_does_not_overwrite_the_first(tmp_path: Path) -> None:
    """A run's definition never changes mid-run, and write_run_manifest calls
    this on every rewrite. The second call here stands in for the second
    manifest write of a run that has moved on to its next step."""
    write_workflow_copy(tmp_path, "run-1", _workflow("first"))

    write_workflow_copy(tmp_path, "run-1", _workflow("second"))

    reread = read_workflow_copy(tmp_path, "run-1")
    assert reread is not None
    assert reread.description == "first"


def test_a_missing_copy_reads_as_none(tmp_path: Path) -> None:
    assert read_workflow_copy(tmp_path, "no-such-run") is None


def test_a_corrupt_copy_reads_as_none_instead_of_raising(tmp_path: Path) -> None:
    path = workflow_copy_path(tmp_path, "run-1")
    path.parent.mkdir(parents=True)
    path.write_text("not json at all")

    assert read_workflow_copy(tmp_path, "run-1") is None


def test_the_payload_written_is_the_workflows_own_json_dump(tmp_path: Path) -> None:
    """Not a wrapper, not a subset: exactly what workflow_definition_payload
    returns, since that is also what the hash in the manifest is built from."""
    workflow = _workflow()

    write_workflow_copy(tmp_path, "run-1", workflow)

    on_disk = workflow_copy_path(tmp_path, "run-1").read_text()
    assert Workflow.model_validate_json(on_disk).model_dump(
        mode="json"
    ) == workflow_definition_payload(workflow)
