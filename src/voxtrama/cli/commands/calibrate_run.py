"""Renders `voxtrama calibrate --run`: the anchoring measures for one run.

Split from calibrate.py to keep both files under the project's 150-line
file limit. The two branches of that command answer different questions and
share nothing but the command's name: calibrate.py's default branch
asks whether the curated corpus is here to calibrate against, and
this one asks whether one run's output is anchored to its transcript.
The measuring is calibration.anchoring's job. This file only turns an
AnchoringReport into the lines the command prints: one line per
RunMaterialStatus case, as calibrate.py's DatasetStatus branches already
do, always at exit code 0.
"""

from __future__ import annotations

import typer

from voxtrama.calibration.anchoring import measure_run
from voxtrama.calibration.anchoring_report import (
    AnchoringMeasure,
    AnchoringReport,
    RunMaterialStatus,
)
from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings


def print_run(run_id: str) -> None:
    """Print the anchoring measures for `run_id`, or, naming it, what is missing.

    measure_run never raises (see its docstring): status names which
    file of the run is missing, and this only turns that into a line and
    stops. Exit code 0 like every other case of `voxtrama calibrate`: a
    run not yet measurable is not this command failing.
    """
    typer.echo(f"Anchoring (run {run_id})")
    paths = get_paths(get_settings().data_dir)
    report = measure_run(paths.runs_dir, run_id)
    if report.status == RunMaterialStatus.MANIFEST_MISSING:
        typer.echo(f"  run {run_id!r} has no manifest.json yet.")
        return
    if report.status == RunMaterialStatus.OUTPUT_MISSING:
        typer.echo(f"  run {run_id!r} has no output.json yet.")
        return
    _print_measured(report)


def _print_measured(report: AnchoringReport) -> None:
    typer.echo("  by step:")
    for step_id, measure in report.per_step.items():
        typer.echo(f"    {step_id:<24} {_render_measure(measure)}")
    if report.skipped_steps:
        noun = "step" if len(report.skipped_steps) == 1 else "steps"
        names = ", ".join(report.skipped_steps)
        typer.echo(f"    ({len(report.skipped_steps)} {noun} with no output, skipped: {names})")
    typer.echo("")
    typer.echo("  by skill:")
    for key, measure in report.per_skill.items():
        label = f"{key.name}@{key.version}"
        typer.echo(f"    {label:<24} {_render_measure(measure)}")


def _render_measure(measure: AnchoringMeasure) -> str:
    """One line: absolute needs_review, coverage as a percent or absent, and determinism."""
    coverage = "n/a (no claims)" if measure.coverage is None else f"{measure.coverage:.0%}"
    determinism = measure.deterministic.value if measure.deterministic else "unknown"
    return (
        f"claims: {measure.claims:<3} needs_review: {measure.needs_review:<3} "
        f"coverage: {coverage:<14} determinism: {determinism}"
    )
