"""Validating `voxtrama run --reuse-from` before anything is imported.

Split out of cli.commands.run only to keep that file under the project's
line limit, the same reason cli.config_errors.data_dir_problem lives in
its own module and not inside the command that calls it.
"""

from __future__ import annotations

import typer
from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run


def check_reuse_from(session: Session, run_id: str | None) -> None:
    """Fail here, naming the id, rather than inside a worker after the audio is imported.

    A no-op for None: engine.enqueue.create_run does not validate
    `reused_from_run_id` at all (see its docstring), so this is the
    one place that does, before any audio is imported or any Run created.
    """
    if run_id is not None and session.get(Run, run_id) is None:
        typer.echo(f"Unknown run to reuse from: {run_id}", err=True)
        raise typer.Exit(code=1)
