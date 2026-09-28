"""The `voxtrama calibrate` command: what material calibration needs, and the anchoring measure.

A badly tuned model does not look badly tuned. It produces
plausible output, and whoever reads it blames the product instead. Without
`--run`, this command only says whether the private material to measure
against exists. Measuring extraction against that corpus is not yet
this command's job. Every case below exits 0: saying the material is missing is
not a failure, and a command that fails on an optional folder teaches
people to stop running it. It runs in CI, where that folder is never
set.

Each of DatasetStatus's cases gets its own message: "not set",
"set but the folder isn't there" and "the folder is there but the corpus
isn't built yet" send a person to fix different things, and one shared
line would mislead at least two of them.

`--run <run_id>` answers a different question (is this run's
output anchored to its transcript?) and short-circuits before any of the
above. The curated corpus is the answer to "is the *content* right",
and `--run` never touches it.
"""

from __future__ import annotations

from typing import Annotated

import typer

from voxtrama.calibration.dataset import (
    REFERENCE_COLUMNS,
    DatasetReport,
    DatasetStatus,
    read_dataset,
)
from voxtrama.cli.commands.calibrate_run import print_run
from voxtrama.config.settings import get_settings

DOC = "docs/evaluation-set.md"


def calibrate_command(
    run: Annotated[
        str | None,
        typer.Option("--run", help="Report the anchoring measures of this run id."),
    ] = None,
) -> None:
    """Report what the curated evaluation set offers, and what is still missing.

    With `--run`, reports the anchoring measures for that run instead,
    and leaves every case below untouched: a run to measure is not
    material to calibrate against, so the two never mix in one report.
    """
    if run is not None:
        print_run(run)
        return
    report = read_dataset(get_settings().eval_dir)

    if report.status == DatasetStatus.UNSET:
        _print_unset()
    elif report.status == DatasetStatus.DIRECTORY_MISSING:
        _print_directory_missing(report)
    elif report.status == DatasetStatus.REFERENCE_MISSING:
        _print_reference_missing(report)
    elif report.status == DatasetStatus.REFERENCE_MALFORMED:
        _print_reference_malformed(report)
    elif not report.annotated:
        _print_unannotated(report)
    else:
        _print_annotated(report)


def _print_unset() -> None:
    typer.echo("Evaluation set")
    typer.echo("  VOXTRAMA_EVAL_DIR is not set.")
    typer.echo("")
    typer.echo("  Calibration measures the configured model against a private set of")
    typer.echo("  recordings you provide: real audio never ships with Voxtrama.")
    typer.echo(f"  Point VOXTRAMA_EVAL_DIR at that folder to use this command; see {DOC}")
    typer.echo("  for how it is built.")


def _print_directory_missing(report: DatasetReport) -> None:
    typer.echo("Evaluation set")
    typer.echo(f"  VOXTRAMA_EVAL_DIR is set to {report.eval_dir}, but that path does not exist.")
    typer.echo("")
    typer.echo("  Create it, or point VOXTRAMA_EVAL_DIR at a folder that does; see")
    typer.echo(f"  {DOC} for how the evaluation set is built.")


def _print_reference_missing(report: DatasetReport) -> None:
    typer.echo("Evaluation set")
    typer.echo(f"  path:         {report.eval_dir}")
    typer.echo("")
    typer.echo("  No reference.csv here yet: this is raw material, not a curated corpus.")
    typer.echo(f"  See {DOC} for the columns it needs and how to add clips/.")


def _print_reference_malformed(report: DatasetReport) -> None:
    typer.echo("Evaluation set")
    typer.echo(f"  path:         {report.eval_dir}")
    typer.echo("")
    typer.echo("  reference.csv does not have the expected columns.")
    typer.echo(f"    expected: {', '.join(REFERENCE_COLUMNS)}")
    typer.echo(f"    found:    {', '.join(report.reference_columns or ()) or '(empty)'}")
    typer.echo(f"  See {DOC} for the exact format.")


def _print_unannotated(report: DatasetReport) -> None:
    _print_header(report)
    if not report.clips:
        typer.echo(f"  reference.csv lists no clips. See {DOC} for the expected layout.")
        return
    typer.echo("  None of them carries an annotation file yet:")
    for clip in report.clips:
        present = "yes" if clip.has_clip else "MISSING"
        typer.echo(f"    {clip.clip:<24} clip: {present:<8} annotation: no")
    typer.echo("")
    typer.echo(f"  Write <clip-stem>.annotation.yaml next to each clip (see {DOC}).")


def _print_annotated(report: DatasetReport) -> None:
    _print_header(report)
    typer.echo(f"  annotated:    {len(report.annotated)} of {len(report.clips)}")
    typer.echo("")
    typer.echo("  Material is here. This command does not measure extraction against it")
    typer.echo("  yet. Anchoring already does, but per")
    typer.echo("  run, not against this corpus (see `voxtrama calibrate --run <run_id>`).")


def _print_header(report: DatasetReport) -> None:
    typer.echo("Evaluation set")
    typer.echo(f"  path:         {report.eval_dir}")
    typer.echo(f"  revision:     {report.revision or 'not declared'}")
    typer.echo(f"  clips:        {len(report.clips)}")
