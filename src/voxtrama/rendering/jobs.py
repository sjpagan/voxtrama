"""The Jobs section's table: one row per job.

Name, Workflow, Audio length, Date, Status. Newest first, no filters.
A running job's status shows how far it got ("3 of 4"),
the same count as the job view's step chain. The name is the job's own
(Run.label), else the file it was made from.

A presenter: every row is built from what the route already read (runs,
their recordings, their step counts), never from its own query.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.humanize import human_clock
from voxtrama.i18n.formatting import format_date
from voxtrama.i18n.translator import Translator

_TONE = {
    RunState.SUCCEEDED: "success",
    RunState.RUNNING: "info",
    RunState.PENDING: "info",
    RunState.FAILED: "danger",
}


@dataclass(frozen=True)
class JobRow:
    """One job as the Jobs table shows it."""

    id: str
    name: str
    workflow: str
    audio_length: str | None
    date: str
    # `run.created_at` is naive but holds UTC (Run.created_at's own
    # default, `datetime.now(UTC)`, loses its tzinfo on the way back out
    # of the database). This is that same instant marked with its offset,
    # so the browser reads it as the UTC it is instead of its own local
    # time (web.static.js.local_time.js turns it into the reader's own).
    date_instant: str
    state: str
    tone: str | None
    progress: tuple[int, int] | None  # (steps done, steps in all), while running
    final: bool
    has_recording: bool


def job_rows(
    runs: list[Run],
    recordings: dict[str, Recording],
    progress: dict[str, tuple[int, int]],
    titles: dict[str, str],
    translator: Translator,
) -> list[JobRow]:
    """Turn already-read runs into table rows, in the order given (newest first)."""
    rows = []
    for run in runs:
        recording = recordings.get(run.recording_id or "")
        state = RunState(str(run.state))
        done, total = progress.get(run.id, (0, 0))
        rows.append(
            JobRow(
                id=run.id,
                name=run.label or (recording.original_filename if recording else run.workflow_name),
                workflow=titles.get(run.workflow_name, run.workflow_name),
                audio_length=human_clock(recording.duration_seconds) if recording else None,
                date=format_date(translator, run.created_at),
                date_instant=run.created_at.replace(tzinfo=UTC).isoformat(),
                state=state.value,
                tone=_TONE.get(state),
                progress=(done, total) if state is RunState.RUNNING and total else None,
                final=state not in (RunState.PENDING, RunState.RUNNING),
                has_recording=recording is not None,
            )
        )
    return rows
