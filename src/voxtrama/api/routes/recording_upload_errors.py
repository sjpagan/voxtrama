"""Turns a file ffprobe rejects into the ProblemException a route returns.

One mapping in one place, shared by every route that imports a file. The
URL errors that lived here went with the URL import itself.
"""

from __future__ import annotations

from fastapi import status

from voxtrama.api.errors import ProblemException
from voxtrama.ingest import UnsupportedMediaError


def unsupported_media_problem(exc: UnsupportedMediaError) -> ProblemException:
    """Map ffprobe's "this is not audio Voxtrama handles" to its problem body.

    recordings.py's own POST /recordings raises this same code today,
    and any other route that ends up calling import_local_file must
    answer with the same one, not a fresh string for the same fact.
    """
    return ProblemException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        code="unsupported_media",
        title="The file is not a supported audio format",
        detail=str(exc),
    )
