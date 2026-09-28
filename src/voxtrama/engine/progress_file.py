"""Where a run says out loud how far it has got.

The database already records what each step did (progress.py), but the CLI
cannot read it: `voxtrama run` enqueues the run and the worker executes it in
another process, against a SQLite file the CLI is not holding open. So the
engine publishes its state as a file inside the run's folder, which is also
what the data directory promises: a run is a folder you can open, and that has to be
true while it is still running, not only afterwards.

The engine writes and does not know who reads. A CLI renders this, an
interface will poll it, and neither is this module's concern.
Activity and ProgressState themselves live in engine.progress_state, split
out to stay under the project's file-length limit.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from voxtrama.engine.activity_log_line import activity_log_line
from voxtrama.engine.activity_words import activity_message
from voxtrama.engine.progress_state import Activity, ProgressState

if TYPE_CHECKING:  # used in signatures only; a real import here would be a cycle
    from voxtrama.db.models.run import Run

PROGRESS_FILENAME = "progress.json"

logger = logging.getLogger(__name__)


def progress_path(runs_dir: Path, run_id: str) -> Path:
    """The progress file of `run_id`, inside that run's folder."""
    return runs_dir / run_id / PROGRESS_FILENAME


def write_progress(runs_dir: Path, state: ProgressState) -> None:
    """Publish `state`, replacing the previous one atomically.

    Atomically because something is reading this file while it is being
    rewritten, several times a second during a download: a reader that
    catches a half-written file would see truncated JSON and have to guess
    whether the run died or the write did.
    """
    target = progress_path(runs_dir, state.run_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(state)
    handle, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def read_progress(runs_dir: Path, run_id: str) -> ProgressState | None:
    """Read the published state of `run_id`, or None if it has not written one.

    A malformed file reads as None instead of raising: this is consumed by
    something that displays progress, and a broken progress file must never
    be the reason a finished run looks failed.

    The same tolerance covers `download` becoming `activity` as a
    rename instead of an addition. A run caught IN FLIGHT during the
    upgrade may have written the old `download` key, which ProgressState no
    longer has a field for. `**payload` then raises TypeError, caught
    below, and this returns None. The run is unaffected, and whoever is
    watching sees "no state" for a moment, which is accepted.
    """
    path = progress_path(runs_dir, run_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    activity = payload.pop("activity", None)
    try:
        return ProgressState(
            **payload, activity=Activity(**activity) if activity is not None else None
        )
    except TypeError:
        return None


def publish_run_state(runs_dir: Path, run: Run, **fields) -> None:
    """Write the run's state where anything that wants to watch can read it.

    Never fatal: a run must not fail because its progress file could not be
    written. What is published is a convenience for whoever is watching.
    The database remains the record of what happened.
    """
    try:
        write_progress(runs_dir, ProgressState(run_id=run.id, state=str(run.state), **fields))
    except OSError:
        logger.warning("could not write progress file")


def activity_reporter(
    runs_dir: Path, run: Run, total: int, index: int, step_id: str, started_at: str | None = None
):
    """Publish activity progress, but not on every step of the loop it comes from.

    Hugging Face reports a download every few kilobytes, and a transcript's
    segments arrive just as often. Writing the file that often would turn
    either into thousands of tiny writes for a reader that refreshes a few
    times a second. One write per percent, plus the last one, carries the
    same information.

    Every throttled write also logs one line
    (engine.activity_log_line), so the terminal panel gains a real,
    advancing line for transcribe and diarize, which had none before.
    A segment count ("segment 5/36") is not available here: `total_amount`
    is a duration or a byte count, not a count of segments faster-whisper
    has not finished producing. So this reports the same position/total
    the live activity bar already shows, not an invented one.
    """
    state = {"last": -1}
    started_at = started_at or datetime.now(UTC).isoformat()  # the page's elapsed time

    def report(name: str, unit: str, done: float, total_amount: float | None) -> None:
        percent = int(done * 100 / total_amount) if total_amount else -1
        if percent == state["last"] and percent not in (-1, 100):
            return
        state["last"] = percent
        message = activity_message(step_id, unit, name)
        publish_run_state(
            runs_dir,
            run,
            step_total=total,
            step_index=index,
            step_id=step_id,
            message=message,
            activity=Activity(name=name, unit=unit, done=done, total=total_amount),
            step_started_at=started_at,
        )
        logger.info(activity_log_line(message, unit, done, total_amount))

    return report
