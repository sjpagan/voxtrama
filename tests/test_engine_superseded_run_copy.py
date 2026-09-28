"""The cascade still holds when the catalogue changes after a run finishes.

test_engine_superseded.py already proves the cascade itself, with `workflow=`
passed straight into superseded_steps: the injection point every other
cascade test uses, which never touches disk at all. This file instead lets
run_a resolve its workflow through the real catalogue
(engine.catalog.load_named_workflow), mutates that catalogue file after
run_a finishes, and only then asks superseded_steps for its default
answer, read from run_a's own runs/<id>/workflow.json
instead of the file that was just mutated.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fakes.catalog_workflow import install_catalog_workflow, write_catalog_workflow
from fakes.reuse_steps import workflow
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.engine.catalog import load_named_workflow
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.engine.superseded import superseded_steps
from voxtrama.manifest.workflow_copy import workflow_copy_path


def _recording(session: Session) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="1" * 64,
        duration_seconds=1.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def test_the_cascade_survives_the_catalogue_changing_after_the_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "t2": 0, "d": 0, "s1": 0, "s2": 0}
    install_catalog_workflow(monkeypatch, calls)
    recording = _recording(db_session)
    write_catalog_workflow(workflow("s1"))

    created_a = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run_a = execute_run(db_session, created_a.id)
    run_a.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.commit()

    # A user's catalogue file may change at any time: flatten "d"
    # and "s" as if someone had edited the file after run_a finished.
    mutated = workflow("s1")
    for step in mutated.steps:
        step.depends_on = []
    write_catalog_workflow(mutated)

    created_b = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run_b = execute_run(db_session, created_b.id, workflow=workflow("s1", transcribe_skill="t2"))
    run_b.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    db_session.commit()

    runs_dir = get_paths(get_settings().data_dir).runs_dir
    # No workflow= here on purpose: this is the reload path, run_a's own
    # workflow.json rather than the catalogue file just mutated above.
    result = superseded_steps(db_session, run_a, runs_dir)

    assert result == {"t": run_b.id, "d": run_b.id, "s": run_b.id}
    # The mutation would have mattered had it been used: reloading straight
    # from the now-flat catalogue drops the cascade down to the direct rule
    # alone, a different and wrong answer for run_a.
    from_catalog = superseded_steps(
        db_session, run_a, runs_dir, workflow=load_named_workflow("test-workflow")
    )
    assert from_catalog == {"t": run_b.id}


def test_a_run_without_a_workflow_copy_falls_back_to_the_catalogue(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run written before runs/<id>/workflow.json existed has none at
    all. Those are not migrated backward, so the cascade must still answer
    from the catalogue exactly as it always did."""
    calls = {"t": 0, "t2": 0, "d": 0, "s1": 0, "s2": 0}
    install_catalog_workflow(monkeypatch, calls)
    recording = _recording(db_session)
    write_catalog_workflow(workflow("s1"))

    created_a = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run_a = execute_run(db_session, created_a.id)
    run_a.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.commit()

    runs_dir = get_paths(get_settings().data_dir).runs_dir
    workflow_copy_path(runs_dir, run_a.id).unlink()

    created_b = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run_b = execute_run(db_session, created_b.id, workflow=workflow("s1", transcribe_skill="t2"))
    run_b.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    db_session.commit()

    result = superseded_steps(db_session, run_a, runs_dir)

    assert result == {"t": run_b.id, "d": run_b.id, "s": run_b.id}
