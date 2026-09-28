"""Composition root for the Voxtrama command-line interface."""

from __future__ import annotations

import typer

from voxtrama.cli.commands import (
    calibrate_command,
    compare_command,
    correct_command,
    demo_command,
    doctor_command,
    retention_command,
    run_command,
    version_command,
)
from voxtrama.cli.config_errors import explain
from voxtrama.config.settings import SettingsError, get_settings
from voxtrama.logs import setup_logging

# Reading settings this early is safe because every variable has a
# working default: no command fails on configuration before it runs. Should a
# value still be malformed, what reaches the terminal is the one line that
# names it, never a pydantic traceback.
try:
    setup_logging(get_settings().log_level)
except SettingsError as exc:  # pragma: no cover - exercised by the CLI, not in-process
    typer.echo(explain(exc), err=True)
    raise SystemExit(2) from exc

app = typer.Typer(name="voxtrama", help="Local-first audio intelligence workflows.")
app.command(name="run")(run_command)
app.command(name="demo")(demo_command)
app.command(name="doctor")(doctor_command)
app.command(name="version")(version_command)
app.command(name="compare")(compare_command)
app.command(name="correct")(correct_command)
app.command(name="calibrate")(calibrate_command)
app.command(name="retention")(retention_command)
