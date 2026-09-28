"""The opaque cursor GET /runs pages with.

Ordering is created_at DESC, then id DESC at equal timestamps: two runs can
be created in the same millisecond, and an order that does not separate
them would skip or repeat a row once paging moves past the tie. The cursor
carries exactly the (created_at, id) pair of the last row a page rendered,
so the next page's filter is unambiguous even across that tie.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime

from fastapi import status
from sqlalchemy import ColumnElement, and_, or_

from voxtrama.api.errors import ProblemException
from voxtrama.db.models.run import Run

_MALFORMED_CURSOR_ERRORS = (
    binascii.Error,
    UnicodeDecodeError,
    json.JSONDecodeError,
    KeyError,
    TypeError,
    ValueError,
)


@dataclass(frozen=True)
class RunCursor:
    """The (created_at, id) position GET /runs orders by, opaque to the client."""

    created_at: datetime
    id: str


def encode_cursor(run: Run) -> str:
    """Encode `run`'s position as the opaque cursor pointing right after it."""
    payload = json.dumps({"created_at": run.created_at.isoformat(), "id": run.id}).encode()
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decode_cursor(raw: str) -> RunCursor:
    """Decode a cursor string, or raise the 422 the route must return.

    Anything that is not base64url(json) in the shape encode_cursor produces
    is the same client mistake (bad base64, bad JSON, a missing field, an
    unparsable timestamp) and gets the same response: a validation failure
    is a request failure, never a 500.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")))
        return RunCursor(created_at=datetime.fromisoformat(payload["created_at"]), id=payload["id"])
    except _MALFORMED_CURSOR_ERRORS as exc:
        raise ProblemException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_failed",
            title="The cursor is malformed",
            detail="cursor could not be decoded",
        ) from exc


def after_cursor(cursor: RunCursor) -> ColumnElement[bool]:
    """The filter for the page after `cursor`, in the same (created_at, id) DESC order."""
    return or_(
        Run.created_at < cursor.created_at,
        and_(Run.created_at == cursor.created_at, Run.id < cursor.id),
    )
