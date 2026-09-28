"""Reconciliation when the catalogue may change after a run finishes.

engine.reconcile_manifest.reloaded_workflow is close_run's own source for the
workflow it rewrites manifest.workflow.definition_sha256 from. Before runs
kept their own workflow copy, that was always
engine.catalog.load_named_workflow, so an interrupted run's rewritten
manifest could end up hashing a *different* definition than the one that
ran, whenever the catalogue changed in between. The run's own copy rules
that out. The first test proves it now holds: run_a finishes, its catalogue
file is mutated, and closing it as interrupted still reproduces the
original hash.

The second proves the review fix that stopped close_run from writing a
false one: a run interrupted before it ever got its own runs/<id>/
workflow.json must not have close_run manufacture one from whatever the
catalogue says by the time reconciliation runs: that copy would then be
indistinguishable from an authentic one to every later reader.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes.catalog_workflow import install_catalog_workflow, write_catalog_workflow
from fakes.reuse_steps import workflow
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.step import RunStep
from voxtrama.engine.catalog import load_named_workflow
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.reconcile_close import close_run
from voxtrama.engine.run import execute_run
from voxtrama.engine.superseded import superseded_steps
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.workflow_copy import workflow_copy_path, workflow_definition_sha256
from voxtrama.manifest.writer import manifest_path


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


def _read_manifest(runs_dir: Path, run_id: str) -> Manifest:
    return Manifest.model_validate_json(manifest_path(runs_dir, run_id).read_text())


def test_a_reconciled_manifest_keeps_the_hash_the_run_actually_had(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "t2": 0, "d": 0, "s1": 0, "s2": 0}
    install_catalog_workflow(monkeypatch, calls)
    recording = _recording(db_session)
    write_catalog_workflow(workflow("s1"))

    created = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run = execute_run(db_session, created.id)
    db_session.commit()

    runs_dir = get_paths(get_settings().data_dir).runs_dir
    original_hash = _read_manifest(runs_dir, run.id).workflow.definition_sha256
    assert original_hash is not None

    # A user's catalogue file may change at any time: give it a
    # different transcribe skill, as if someone had edited the file after
    # run finished.
    write_catalog_workflow(workflow("s1", transcribe_skill="t2"))
    mutated_hash = workflow_definition_sha256(load_named_workflow("test-workflow"))
    assert mutated_hash != original_hash

    # Simulates the worker that ran `run` dying: reconcile_orphan_runs
    # would find it exactly this way, mid-`running`, and hand it to
    # close_run the same way.
    run.state = RunState.RUNNING
    db_session.commit()
    rows = db_session.scalars(select(RunStep).where(RunStep.run_id == run.id)).all()
    assert rows

    close_run(db_session, runs_dir, run, RunState.INTERRUPTED)

    assert _read_manifest(runs_dir, run.id).workflow.definition_sha256 == original_hash


def test_an_interrupted_run_without_a_copy_never_gains_a_false_one(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "t2": 0, "d": 0, "s1": 0, "s2": 0}
    install_catalog_workflow(monkeypatch, calls)
    recording = _recording(db_session)
    write_catalog_workflow(workflow("s1"))

    # Interrupted before it ever ran a step: the shape every run written
    # before runs kept a workflow copy has: no manifest, no workflow.json, nothing but the row.
    run = Run(
        workflow_name="test-workflow",
        workflow_version="1.0.0",
        state=RunState.RUNNING,
        recording_id=recording.id,
        started_at=datetime.now(UTC),
    )
    db_session.add(run)
    db_session.commit()
    runs_dir = get_paths(get_settings().data_dir).runs_dir

    # The catalogue may change at any time, even under a run
    # that never got the chance to observe it running.
    write_catalog_workflow(workflow("s1", transcribe_skill="t2"))

    close_run(db_session, runs_dir, run, RunState.INTERRUPTED)

    assert manifest_path(runs_dir, run.id).is_file()
    assert not workflow_copy_path(runs_dir, run.id).exists()
    # Unaffected by the fix: with no copy to prefer, the cascade keeps
    # reading the catalogue for this run, exactly as it does today for
    # every run written before runs kept a workflow copy.
    assert superseded_steps(db_session, run, runs_dir) == {}
