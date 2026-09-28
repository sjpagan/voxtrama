"""Computes anchoring measures for a run already on disk.

`engine.anchoring` writes `evidence` and `needs_review` onto every claim of
a step's output while the run executes (see that module's own docstring).
This file locates a run's manifest.json and output.json and decides which
RunMaterialStatus the run is in. The per-step walk that turns a resolved
pair of the two into per_step/per_skill/skipped_steps is
calibration/anchoring_walk.py's job, split out for the project's line
limits. The result's shape (AnchoringMeasure, AnchoringReport,
RunMaterialStatus, SkillKey) lives in calibration/anchoring_report.py. That
file's docstring explains why the split runs there too.

This module's reference is the run's own transcript, the same one
engine.anchoring already checked every claim against, and not the curated
annotated corpus calibration.dataset inspects. So this measure does not
wait on that corpus: the material it needs already exists on every run.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.calibration.anchoring_report import AnchoringReport, RunMaterialStatus
from voxtrama.calibration.anchoring_walk import walk_steps
from voxtrama.manifest.output import read_run_output
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path


def measure_run(runs_dir: Path, run_id: str) -> AnchoringReport:
    """Compute anchoring measures for `run_id`, reading only what is already on disk.

    Never raises: manifest.json or output.json not yet on disk is itself
    the fact `status` reports (RunMaterialStatus), not an exception a
    caller has to catch. For a run that does not
    exist, and one that has not produced anything yet, `status` names
    which of the two, as calibration.dataset.DatasetStatus does for the
    curated corpus.
    """
    manifest = _read_manifest(runs_dir, run_id)
    if manifest is None:
        return _missing(RunMaterialStatus.MANIFEST_MISSING)
    output = read_run_output(runs_dir, run_id)
    if output is None:
        return _missing(RunMaterialStatus.OUTPUT_MISSING)
    return walk_steps(manifest, output)


def _missing(status: RunMaterialStatus) -> AnchoringReport:
    return AnchoringReport(status=status, per_step={}, per_skill={}, skipped_steps=())


def _read_manifest(runs_dir: Path, run_id: str) -> Manifest | None:
    """The run's manifest, or None when it is not on disk yet. Never raises."""
    path = manifest_path(runs_dir, run_id)
    if not path.is_file():
        return None
    return Manifest.model_validate_json(path.read_text())
