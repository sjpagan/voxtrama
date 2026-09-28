"""writer.py: what reaches disk, and how stable it is.

build_manifest's own behaviour is covered in test_manifest_builder.py and
test_manifest_sections.py. This file is only about serialization and the
atomic write.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from voxtrama.db.models.run import Run
from voxtrama.manifest.workflow_copy import workflow_copy_path
from voxtrama.manifest.writer import manifest_path, sha256_of_file, write_run_manifest
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow


def _workflow() -> Workflow:
    return Workflow(
        name="demo",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="transcribe", skill="transcribe", skill_version="1.0.0")],
    )


def _run(run_id: str, created_at: datetime) -> Run:
    return Run(
        id=run_id,
        workflow_name="demo",
        workflow_version="1.0.0",
        state=JobState.RUNNING,
        created_at=created_at,
    )


def test_the_manifest_lives_in_the_run_own_folder(tmp_path):
    """A run is a folder you can open, while it runs and after."""
    run = _run("r1", datetime(2026, 1, 1, tzinfo=UTC))
    write_run_manifest(tmp_path, run, [], _workflow(), {}, None, None)

    assert manifest_path(tmp_path, "r1").parent.name == "r1"


def test_two_runs_on_the_same_input_produce_byte_identical_manifests(tmp_path):
    """Two runs compare with `diff`, once their ids and times are normalized."""
    workflow = _workflow()
    run_a = _run("run-a", datetime(2026, 1, 1, tzinfo=UTC))
    run_b = _run("run-b", datetime(2026, 1, 2, tzinfo=UTC))
    write_run_manifest(tmp_path, run_a, [], workflow, {}, None, None)
    write_run_manifest(tmp_path, run_b, [], workflow, {}, None, None)

    first = json.loads(manifest_path(tmp_path, "run-a").read_text())
    second = json.loads(manifest_path(tmp_path, "run-b").read_text())
    for payload in (first, second):
        payload["run"]["id"] = "RUN_ID"
        payload["run"]["created_at"] = "T"
        # destination.path embeds the run id too (runs/<run_id>/),
        # the same identifier normalized above, not a second thing.
        payload["run"]["destination"]["path"] = "runs/RUN_ID"

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_a_rewrite_is_never_seen_half_written(tmp_path):
    """Written to a temporary file and renamed: a reader sees old or new, never both."""
    run = _run("r1", datetime(2026, 1, 1, tzinfo=UTC))
    write_run_manifest(tmp_path, run, [], _workflow(), {}, None, None)
    run.state = JobState.SUCCEEDED
    write_run_manifest(tmp_path, run, [], _workflow(), {}, None, None)

    payload = json.loads(manifest_path(tmp_path, "r1").read_text())
    assert payload["run"]["state"] == "succeeded"
    # Exactly the manifest and the workflow copy: no leftover .tmp
    # file from either atomic write.
    present = set(manifest_path(tmp_path, "r1").parent.iterdir())
    assert present == {manifest_path(tmp_path, "r1"), workflow_copy_path(tmp_path, "r1")}


def test_sha256_of_file_hashes_in_chunks(tmp_path):
    """For the outputs a future skill will produce (outputs[] is empty today)."""
    path = tmp_path / "f.bin"
    path.write_bytes(b"hello world")

    assert sha256_of_file(path) == hashlib.sha256(b"hello world").hexdigest()
