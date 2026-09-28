"""The JSON formatter: one log line in, one JSON object out.

The only place that decides what leaves the process. It reads the
allow-list from logs.fields and drops everything else. There are no
exceptions and no per-call override, because the guarantee is only as
strong as this function's refusal to make one.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from voxtrama.logs.context import current_context
from voxtrama.logs.fields import EXTRA_FIELDS


class JsonFormatter(logging.Formatter):
    """Renders a LogRecord as one JSON line, emitting only allowed fields."""

    def format(self, record: logging.LogRecord) -> str:
        event = {
            "ts": _timestamp(record),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        event.update(current_context())
        for field in EXTRA_FIELDS:
            if field in record.__dict__:
                event[field] = record.__dict__[field]
        return json.dumps(event, ensure_ascii=False)


def _timestamp(record: logging.LogRecord) -> str:
    """UTC, ISO 8601, millisecond precision."""
    moment = datetime.fromtimestamp(record.created, tz=UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"
