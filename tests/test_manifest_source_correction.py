"""A corrected source_title never rewrites a manifest already on disk.

This test compares the bytes themselves. The manifest is
something meant to be copied and attached, so two copies of one run's
manifest (one taken before a correction, one after) must be identical
down to the byte, never merely "look the same".
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.recordings import correct_source
from voxtrama.manifest.writer import manifest_path, write_run_manifest
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


def test_correcting_a_recording_does_not_change_its_run_manifest_on_disk(
    tmp_path: Path, db_session: Session
) -> None:
    recording = Recording(
        id="rec1",
        original_filename="clip.opus",
        stored_path="recordings/rec1/clip.opus",
        content_sha256="0" * 64,
        duration_seconds=10.0,
        media_format="opus",
        source_title="A Creative Commons clip",
        source_url="https://example.com/watch?v=abc123",
    )
    db_session.add(recording)
    db_session.commit()

    run = Run(
        id="run-1",
        workflow_name="demo",
        workflow_version="1.0.0",
        state=JobState.RUNNING,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    write_run_manifest(tmp_path, run, [], _workflow(), {}, recording, None)
    path = manifest_path(tmp_path, "run-1")
    before_bytes = path.read_bytes()
    before_sha256 = hashlib.sha256(before_bytes).hexdigest()

    corrected = correct_source(db_session, "rec1", source_title="The actual title")
    assert corrected.source_title == "The actual title"

    after_bytes = path.read_bytes()
    after_sha256 = hashlib.sha256(after_bytes).hexdigest()

    assert after_bytes == before_bytes
    assert after_sha256 == before_sha256
