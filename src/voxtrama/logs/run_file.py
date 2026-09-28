"""The copy of a run's log lines inside its own runs/<run_id>/ folder.

A run folder is something you can open on its own, so the lines that
belong to a run go inside it, in addition to stdout and
never instead of it, so a disk problem never silences the diagnostics
that are still reaching the container's log driver.
"""

from __future__ import annotations

import logging
from pathlib import Path

from voxtrama.logs.context import current_context

# Named once, not a literal repeated in logs.tail (the reader) and here
# (the writer): both have to agree on the one file a run's own folder
# carries its log lines under.
RUN_LOG_FILENAME = "run.log"


class RunFileHandler(logging.Handler):
    """Appends formatted lines carrying a run_id to <runs_dir>/<run_id>/run.log.

    Does nothing when the current context has no run_id: most lines are
    produced outside any run. Never lets a write failure propagate: this
    handler runs alongside a stdout handler, and a full disk here must not
    take the stdout line down with it.
    """

    def __init__(self, runs_dir: Path) -> None:
        super().__init__()
        self._runs_dir = runs_dir

    def emit(self, record: logging.LogRecord) -> None:
        run_id = current_context().get("run_id")
        if run_id is None:
            return
        try:
            run_dir = self._runs_dir / run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            with (run_dir / RUN_LOG_FILENAME).open("a", encoding="utf-8") as handle:
                handle.write(self.format(record) + "\n")
        except OSError:
            self.handleError(record)
