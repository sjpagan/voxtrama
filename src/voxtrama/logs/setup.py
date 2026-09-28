"""Wires the JSON formatter into Python's logging, once per process.

Called by each entrypoint's composition root, never by library code.
Library code only ever calls logging.getLogger(__name__).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from voxtrama.logs.formatter import JsonFormatter
from voxtrama.logs.run_file import RunFileHandler


def setup_logging(level: str = "INFO", runs_dir: Path | None = None) -> None:
    """Route every log line through the JSON formatter, on stdout.

    With `runs_dir`, lines carrying a run_id are also appended under it.
    Safe to call more than once: it replaces the root logger's
    handlers rather than stacking them.
    """
    formatter = JsonFormatter()

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [stdout_handler]

    if runs_dir is not None:
        run_file_handler = RunFileHandler(runs_dir)
        run_file_handler.setFormatter(formatter)
        handlers.append(run_file_handler)

    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers = handlers
