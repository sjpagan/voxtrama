"""What the "Preparing local processing" downloading panel shows:
turns a ProgressState (published by
worker.tasks.download_model_job through setup.download_progress) into
the bar, the byte counts and the status lines the template renders, so
the template computes none of them.

No estimated time remaining: a rate needs two points in time, and
ProgressState only carries the latest one (`updated_at` alone, no
history). A number from a single sample would be a guess, the same kind
that is never made about a hardware profile, applied to a duration
instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.engine.progress_state import ProgressState
from voxtrama.humanize import human_bytes


@dataclass(frozen=True)
class DownloadView:
    """The downloading panel's fields, exactly as the template shows them."""

    model_label: str
    done_label: str
    total_label: str
    percent: int
    log_lines: list[str]
    failed: bool
    message: str | None
    queued: bool = False  # Waiting for the worker, no byte counts yet


def download_view(state: ProgressState) -> DownloadView:
    activity = state.activity
    done = activity.done if activity else 0
    total = activity.total if activity else None
    percent = int(done * 100 / total) if total else 0
    label = activity.name if activity else "model"
    total_label = human_bytes(total) if total else "unknown"
    lines = [f"Resolving {label} from the local model registry"]
    if state.state == "running":
        lines.append(f"{human_bytes(done)} / {total_label}")
    return DownloadView(
        model_label=label,
        done_label=human_bytes(done),
        total_label=total_label,
        percent=percent,
        log_lines=lines,
        failed=state.state == "failed",
        message=state.message,
        queued=state.state == "queued",
    )
