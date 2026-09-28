"""The `voxtrama version` command."""

from __future__ import annotations

import typer

from voxtrama import __version__


def version_command() -> None:
    """Print the installed Voxtrama package version."""
    typer.echo(__version__)
