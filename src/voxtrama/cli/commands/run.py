"""The `voxtrama run` command: announce, enqueue, and follow a Run to its end.

The run executes in the worker: this process only watches, reading the
state the engine publishes into the run's folder. That is enough to follow
a run it did not start, or walk away from with --detach.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy.orm import Session

from voxtrama.cli.announce import announce_downloads, announce_estimate
from voxtrama.cli.config_errors import data_dir_problem
from voxtrama.cli.progress_view import follow_run
from voxtrama.cli.reuse_from import check_reuse_from
from voxtrama.config.paths import Paths, get_paths
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.people import local_user
from voxtrama.db.session import build_session_factory, session_scope
from voxtrama.engine.catalog import WorkflowNotFoundError, load_named_workflow
from voxtrama.engine.enqueue import enqueue_run
from voxtrama.ingest import UnsupportedMediaError, import_local_file
from voxtrama.queue.rq_backend import RQBackend
from voxtrama.workflow.definition import Workflow
from voxtrama.workflow.errors import WorkflowError


def _build_queue() -> RQBackend:
    """Build the queue backend for this invocation of the CLI."""
    return RQBackend(get_settings().queue_url)


def _import_and_enqueue(
    session: Session,
    workflow_name: str,
    workflow: Workflow,
    audio: str,
    paths: Paths,
    settings: Settings,
    reuse_from: str | None,
) -> str:
    """Import the audio, announce its estimate, enqueue the Run, return its id.

    Split out of run_command to keep it under the project's 40-line body limit.
    `audio` is a local file; `reuse_from` is already checked by check_reuse_from.
    """
    created_by = local_user(session).id
    try:
        recording = import_local_file(session, Path(audio), paths, created_by=created_by)
    except UnsupportedMediaError as exc:
        typer.echo(f"Unsupported media: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    announce_estimate(recording.duration_seconds, settings.hardware_profile, workflow, paths)
    # Create-then-submit is the one sequence in engine.enqueue.
    created, _job_id = enqueue_run(
        session,
        _build_queue(),
        workflow_name,
        workflow,
        recording_id=recording.id,
        created_by=created_by,
        reused_from_run_id=reuse_from,
    )
    return created.id


def run_command(
    workflow_name: Annotated[str, typer.Argument(help="Name of the workflow to run.")],
    audio: Annotated[str, typer.Argument(help="Path to the audio file.")],
    detach: Annotated[
        bool, typer.Option("--detach", help="Print the run id and exit instead of following it.")
    ] = False,
    reuse_from: Annotated[
        str | None, typer.Option("--reuse-from", help="Run id to reuse matching step outputs from.")
    ] = None,
) -> None:
    """Validate the audio file, import it, enqueue a Run, and follow it to its end."""
    if not Path(audio).exists():
        typer.echo(f"Audio file not found: {audio}", err=True)
        raise typer.Exit(code=1)

    workflow = _load_workflow(workflow_name)

    settings = get_settings()
    _require_usable_data_dir(settings)
    paths = get_paths(settings.data_dir)
    announce_downloads(workflow, settings.hardware_profile, paths.models_dir)

    with session_scope(build_session_factory()) as session:
        check_reuse_from(session, reuse_from)
        run_id = _import_and_enqueue(
            session, workflow_name, workflow, audio, paths, settings, reuse_from
        )

    typer.echo(run_id)

    if detach:
        return
    final_state = follow_run(paths.runs_dir, run_id)
    if final_state is None:
        typer.echo("Still queued: no worker has picked it up. The run is not lost.")
        return
    if final_state == "failed":
        raise typer.Exit(code=1)


def _require_usable_data_dir(settings: Settings) -> None:
    """Fail here, naming the variable, instead of deeper with an OSError."""
    problem = data_dir_problem(settings)
    if problem is not None:
        typer.echo(problem, err=True)
        raise typer.Exit(code=1)


def _load_workflow(workflow_name: str) -> Workflow:
    """Load the named workflow, or fail in front of whoever typed the name.

    Before anything is imported or enqueued: a name that does not exist,
    or a file that does not validate, must fail here, not inside a worker.
    """
    try:
        return load_named_workflow(workflow_name)
    except WorkflowNotFoundError as exc:
        typer.echo(f"Unknown workflow: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except WorkflowError as exc:
        typer.echo(f"Invalid workflow: {exc}", err=True)
        raise typer.Exit(code=1) from exc
