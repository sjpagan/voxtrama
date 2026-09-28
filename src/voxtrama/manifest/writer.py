"""Serializes a Manifest to stable JSON and writes it atomically.

builder.py assembles the Manifest from a Run's own rows. Everything here
only turns that value into bytes on disk. Split so neither file grows past
the project's size limit. See builder.py's docstring for the other half.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.db.models.step import RunStep
from voxtrama.db.models.transcript import Transcript
from voxtrama.manifest.builder import build_manifest
from voxtrama.manifest.evidence import ClaimCount
from voxtrama.manifest.jsonfile import write_atomic
from voxtrama.manifest.workflow_copy import write_workflow_copy
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.loader import SkillRegistry

MANIFEST_FILENAME = "manifest.json"
_HASH_CHUNK_SIZE = 1 << 20

logger = logging.getLogger(__name__)


def manifest_path(runs_dir: Path, run_id: str) -> Path:
    """The manifest of `run_id`, inside that run's own folder."""
    return runs_dir / run_id / MANIFEST_FILENAME


def sha256_of_file(path: Path) -> str:
    """Hash `path` in chunks, for the outputs recorded in manifest.outputs[].

    Used by write_run_manifest's caller to verify the digest write_run_output
    returned still matches the file on disk (run comparison and the gold
    dataset lean on the same guarantee), and it belongs next to the schema
    it hashes for.
    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def write_run_manifest(
    runs_dir: Path,
    run: Run,
    rows: list[RunStep],
    workflow: Workflow | None,
    skills: SkillRegistry,
    recording: Recording | None,
    transcript: Transcript | None,
    evidence: dict[str, ClaimCount] | None = None,
    produced: dict[str, dict[str, Any]] | None = None,
    output_digest: str | None = None,
    workflow_from_run: bool = True,
) -> None:
    """Build and publish the manifest for `run`, tolerating a write failure.

    Never fatal, for the same reason publish_run_state (progress_file.py)
    is not: a run that is otherwise going well must not fail because its
    manifest could not be written.

    Also writes the run's own workflow copy whenever
    `workflow` is resolved and `workflow_from_run` says it may: the copy
    exists to prove what a run executed, so only a caller that is itself
    watching that execution (engine.stepping, engine.failure, both
    defaulting True here) may write one. `workflow_from_run=False` is for
    a caller like engine.reconcile_close: it never ran anything, only
    reloaded a definition after the fact, and when that reload falls back
    to the catalogue (engine.reconcile_manifest.reloaded_workflow, no copy
    already on disk) the definition it holds is only whatever the
    catalogue says *now*. Writing it as this run's copy would make a
    reader believe that is what the run executed: the false
    attestation this exists to prevent.
    """
    manifest = build_manifest(
        run,
        rows,
        workflow,
        skills,
        recording,
        transcript,
        evidence,
        produced,
        output_digest=output_digest,
    )
    try:
        write_atomic(manifest.model_dump(mode="json"), manifest_path(runs_dir, run.id))
    except OSError:
        logger.warning("could not write run manifest")
    if workflow is not None and workflow_from_run:
        write_workflow_copy(runs_dir, run.id, workflow)
