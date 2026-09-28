"""The `voxtrama compare` command: two manifests in, a diff-style report out.

The whole comparison lives in manifest.comparison (core); this file only
turns two command-line arguments into the two Paths it reads, and turns its
CompareResult into stdout lines and an exit code. It is the same split
run_command keeps between "find the input" and "run the engine".
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from voxtrama.manifest.comparison.report import ManifestReadError, compare, load_manifest
from voxtrama.manifest.writer import MANIFEST_FILENAME


def compare_command(
    a: Annotated[Path, typer.Argument(help="First manifest, or a run folder with manifest.json.")],
    b: Annotated[Path, typer.Argument(help="Second manifest, or a run folder with manifest.json.")],
    show_expected: Annotated[
        bool,
        typer.Option("--show-expected", help="Also list the differences the catalog expects."),
    ] = False,
) -> None:
    """Compare two run manifests and report the differences that count."""
    try:
        manifest_a = load_manifest(_resolve(a))
        manifest_b = load_manifest(_resolve(b))
        result = compare(manifest_a, manifest_b, show_expected=show_expected)
    except ManifestReadError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    for line in result.lines:
        typer.echo(line)
    if result.exit_code:
        raise typer.Exit(code=result.exit_code)


def _resolve(path: Path) -> Path:
    """`path` itself, or `path/manifest.json` when `path` is a run folder."""
    return path / MANIFEST_FILENAME if path.is_dir() else path
