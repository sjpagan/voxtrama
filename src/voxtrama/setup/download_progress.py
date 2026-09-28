"""Where the guided setup's model download reports itself.

Reuses engine.progress_file's write_progress/read_progress instead of
inventing a second channel. The mechanism a Run's progress already uses
(one JSON file, replaced atomically, read by whatever polls it) has
nothing Run-specific in its signature. The "run_id" it is keyed on here is
a fixed slot name instead of a real Run id, because the guided setup only
downloads one model at a time. `data_dir` stands in for `runs_dir`, so
this lives at `<data_dir>/setup-model-download/`, a sibling of `runs/`,
`models/` and the rest of the data directory's layout, not inside it.

The queue job's id lives in a second, tiny sidecar file next to the
progress one. ProgressState has no field for it (no other reader of a
progress file needs a queue job id), and "Cancel download" needs it to
call queue.cancel().
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.engine.progress_file import progress_path, read_progress, write_progress
from voxtrama.engine.progress_state import Activity, ProgressState

DOWNLOAD_SLOT = "setup-model-download"
JOB_ID_FILENAME = "job_id.txt"

# The two states a poller treats as "still going". Anything else
# ("succeeded", "failed", "cancelled") means the page stops refreshing.
IN_PROGRESS_STATES = frozenset({"queued", "running"})


def _slot_dir(data_dir: Path) -> Path:
    return progress_path(data_dir, DOWNLOAD_SLOT).parent


def publish_download_state(
    data_dir: Path,
    state: str,
    *,
    model_label: str | None = None,
    done_bytes: float | None = None,
    total_bytes: float | None = None,
    message: str | None = None,
) -> None:
    """Publish the download's state: "queued", "running", "succeeded", "failed", "cancelled"."""
    activity = None
    if model_label is not None:
        activity = Activity(name=model_label, unit="bytes", done=done_bytes or 0, total=total_bytes)
    write_progress(
        data_dir,
        ProgressState(run_id=DOWNLOAD_SLOT, state=state, message=message, activity=activity),
    )


def read_download_state(data_dir: Path) -> ProgressState | None:
    """The download's last-published state, or None if nothing has run yet."""
    return read_progress(data_dir, DOWNLOAD_SLOT)


def write_download_job_id(data_dir: Path, job_id: str) -> None:
    slot = _slot_dir(data_dir)
    slot.mkdir(parents=True, exist_ok=True)
    (slot / JOB_ID_FILENAME).write_text(job_id)


def read_download_job_id(data_dir: Path) -> str | None:
    try:
        return (_slot_dir(data_dir) / JOB_ID_FILENAME).read_text().strip() or None
    except OSError:
        return None
