"""Turning a run's published state into something a person can watch.

The engine writes progress.json inside the run's folder; this reads it and
prints it. The split follows the project's layering (the engine has no
idea a CLI exists), and it also lets `voxtrama run` follow a run that a worker is executing in
another process.

Two renderings, chosen by whether stdout is a terminal. A bar that rewrites
its own line is right in front of a person and unreadable in a log file,
where every redraw becomes another line of control characters.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import typer

from voxtrama.cli.progress_lines import describe_run_line
from voxtrama.db.models.run import RunState, is_final
from voxtrama.engine.progress_file import ProgressState, read_progress

# Derived from is_final, not a second hand-written list: that
# mismatch used to leave `cancelled`/`interrupted` runs followed forever.
TERMINAL_STATES = {state.value for state in RunState if is_final(state)}
POLL_SECONDS = 0.4
# How long to wait for the worker to publish anything. A run may take an
# hour and that is fine. This only bounds the silence before it starts,
# which is the case where no worker is listening.
SILENCE_SECONDS = 30.0


@dataclass
class ProgressPrinter:
    """Prints run progress, once per change, in one of two styles."""

    interactive: bool
    last_line: str = ""

    def render(self, state: ProgressState) -> None:
        line = describe_run_line(state, self.interactive)
        if line == self.last_line:
            return
        self.last_line = line
        if self.interactive:
            # \r plus padding: the previous line may have been longer, and a
            # leftover tail of it would read as part of the new one.
            typer.echo(f"\r{line:<78}", nl=False)
        else:
            typer.echo(line)

    def finish(self, state: ProgressState) -> None:
        """Close the display, leaving the final line visible."""
        if self.interactive:
            typer.echo(f"\r{describe_run_line(state, self.interactive):<78}")


def follow_run(
    runs_dir: Path,
    run_id: str,
    timeout_seconds: float | None = None,
    silence_seconds: float = SILENCE_SECONDS,
) -> str | None:
    """Print a run's progress until it reaches a terminal state.

    Returns the final state, or None if it gave up watching first. Giving up
    is not cancelling: the run stays queued and the worker will execute it,
    and the caller has to say so instead of implying otherwise.

    Two different waits, and conflating them was a bug. A run may
    legitimately take an hour, so there is no deadline on the run. What
    is bounded is the silence *before* it starts: if nothing has published
    anything after `silence_seconds`, nobody is executing this run (no
    worker is listening), and waiting forever helps no one.
    """
    printer = ProgressPrinter(interactive=sys.stdout.isatty())
    started = time.monotonic()
    last: ProgressState | None = None
    while timeout_seconds is None or time.monotonic() - started < timeout_seconds:
        state = read_progress(runs_dir, run_id)
        if state is not None:
            last = state
            printer.render(state)
            if state.state in TERMINAL_STATES:
                printer.finish(state)
                return state.state
        elif time.monotonic() - started > silence_seconds:
            return None
        time.sleep(POLL_SECONDS)
    if last is not None:
        printer.finish(last)
    return None
