"""Turning a fired timeout into a message that names its real cause.

Split from engine.timeout, which decides how long a job may run: this
decides what to say once that budget is spent. A run's timeout can fire
while waiting on a model download or while processing audio, and RQ's
message cannot tell them apart because it only knows the number it was
given. This reads the run's progress file, the one the CLI follows,
to find out which it was.
"""

from __future__ import annotations

from pathlib import Path

# RQ's timeout fires via a signal wherever the job is executing at the
# time, so only code running then can tell a timeout from any other
# failure. Nothing in queue.rq_backend is on the call stack at that point.
# A deliberate, narrow exception to "only rq_backend imports rq" (see its
# docstring).
from rq.timeouts import JobTimeoutException

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run
from voxtrama.engine.progress_file import Activity, read_progress
from voxtrama.humanize import human_bytes
from voxtrama.queue.errors import JobTimeoutError


def describe_if_timeout(
    exc: Exception, run: Run, recording: Recording | None, runs_dir: Path
) -> Exception:
    """Replace RQ's timeout message with one naming its real cause.

    Returns `exc` unchanged for every other kind of failure. A download in
    progress when the signal fired takes priority over the audio message:
    a run that dies fetching a model was never wrong about the audio, and
    saying so would send someone looking in the wrong place.
    """
    if not isinstance(exc, JobTimeoutException):
        return exc
    granted = run.job_timeout_seconds
    download = _active_download(runs_dir, run.id)
    if granted is not None and download is not None:
        return JobTimeoutError(_download_message(granted, download))
    duration = recording.duration_seconds if recording else None
    if duration is None or granted is None:
        return JobTimeoutError(str(exc))
    return JobTimeoutError(f"job timed out after {granted}s, granted for {duration:.0f}s of audio")


def _active_download(runs_dir: Path, run_id: str) -> Activity | None:
    """The download the run's progress file last reported, or None.

    Read rather than tracked separately: the last state a run published is
    also the last thing it was doing when the signal interrupted it. A
    missing or stale file (nothing written, or a download that had already
    finished when the signal fired) reads as "no download" and falls back
    to the audio message, the safer guess of the two.

    Filtered to unit == "bytes": the same activity channel also carries a
    transcription's position. Reporting a transcription as a
    download would send someone looking at a model that finished fetching
    minutes ago.
    """
    state = read_progress(runs_dir, run_id)
    if state is None or state.activity is None or state.activity.unit != "bytes":
        return None
    return state.activity


def _download_message(granted: int, download: Activity) -> str:
    if download.total is None:
        return (
            f"job timed out after {granted}s while downloading {download.name}: "
            f"{human_bytes(download.done)} fetched, total unknown"
        )
    remaining = download.total - download.done
    return (
        f"job timed out after {granted}s while downloading {download.name}: "
        f"{human_bytes(remaining)} of {human_bytes(download.total)} still missing"
    )
