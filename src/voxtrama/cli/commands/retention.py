"""The `voxtrama retention` command: prove what retention deleted.

Lists every job whose content retention deleted, when and under which
limit, and says for each that nothing of it is left on disk or in the
database, or what is. Exit code 1 when anything is left.
"""

from __future__ import annotations

import typer

from voxtrama.config.settings import get_settings
from voxtrama.db.session import build_session_factory, session_scope
from voxtrama.housekeeping.retention_proof import check_tombstones


def retention_command() -> None:
    """List the jobs retention emptied and show that nothing of them is left."""
    settings = get_settings()
    limit = f"{settings.retention_days} days" if settings.retention_days else "none"
    typer.echo(f"Installation limit: {limit}")
    with session_scope(build_session_factory()) as session:
        checks = check_tombstones(session, settings.data_dir)
    if not checks:
        typer.echo("No job has been deleted by retention.")
        return
    for check in checks:
        rule = f"{check.retention_days} days ({check.retention_level})"
        state = "nothing left" if not check.leftovers else "LEFT: " + ", ".join(check.leftovers)
        typer.echo(f"{check.run_id}  deleted {check.deleted_at}  under {rule}  {state}")
    if any(check.leftovers for check in checks):
        raise typer.Exit(code=1)
