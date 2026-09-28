"""Capturing one logger's own records, deaf to global logging state.

`caplog` relies on a handler pytest attaches to the root logger; that stops
working the moment something elsewhere in the same process calls
logging.config.dictConfig with its default disable_existing_loggers=True
(uvicorn's own startup does), which sets `.disabled = True` on every logger
that already existed, a short-circuit `caplog` never sees past. A handler
attached directly to the logger under test, with `.disabled` forced back to
False for the duration, does not depend on any of that.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager


class _Collector(logging.Handler):
    """A handler that just keeps every record it receives, in order."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextmanager
def capture_logger(logger_name: str) -> Iterator[list[logging.LogRecord]]:
    """Every record `logger_name` emits during the block."""
    logger = logging.getLogger(logger_name)
    handler = _Collector()
    original_level, original_disabled = logger.level, logger.disabled
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(handler)
    try:
        yield handler.records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.disabled = original_disabled
