"""What a run says before it starts: what it will fetch, and how long it will take.

A standing rule of the project, in two sentences printed before the first byte
moves: "an announced wait is a wait, an unannounced wait is a fault".
They live here and not in the command because `run` and `demo` both
print them, and because the command was already at the size the project's
file limit allows.
"""

from __future__ import annotations

from pathlib import Path

import typer

from voxtrama.config.paths import Paths
from voxtrama.engine.downloads import pending_downloads
from voxtrama.engine.estimate import estimate_download_seconds, estimate_processing_seconds
from voxtrama.humanize import human_bytes, human_duration
from voxtrama.workflow.definition import Workflow


def announce_downloads(workflow: Workflow, profile: str, models_dir: Path) -> None:
    """Say what will be downloaded, before the first byte moves.

    Said here and not by the worker: the worker's output goes to a log
    nobody has opened, while the person who typed the command is watching
    this terminal and about to conclude it has hung.
    """
    pending = pending_downloads(workflow, profile, models_dir)
    if not pending:
        return
    total = sum(item.nominal_bytes for item in pending)
    names = ", ".join(item.label for item in pending)
    typer.echo(
        f"First run on this machine: about {human_bytes(total)} to download ({names}). "
        "Fetched once, reused afterwards."
    )


def announce_estimate(duration: float, profile: str, workflow: Workflow, paths: Paths) -> None:
    """Say roughly how long this will take, before it starts.

    Separate from the byte count above because it needs the audio's
    duration, which is only known once the file has been imported. Both
    halves still land before any real work begins.
    """
    missing = sum(
        item.nominal_bytes for item in pending_downloads(workflow, profile, paths.models_dir)
    )
    processing = estimate_processing_seconds(duration, profile)
    if missing:
        # Two numbers, not one total: "about 10 minutes for 13 seconds of
        # audio" reads as a product that is absurdly slow, when almost all
        # of it is a download that happens once.
        typer.echo(
            f"About {human_duration(estimate_download_seconds(missing))} to fetch them, "
            f"then about {human_duration(processing)} to process "
            f"{human_duration(duration)} of audio."
        )
        return
    typer.echo(
        f"About {human_duration(processing)} expected for {human_duration(duration)} of audio."
    )
