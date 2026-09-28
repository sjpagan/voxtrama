"""Parsing a single-range `Range: bytes=...` header into concrete file offsets.

Split from recording_audio.py: turning header text into a byte interval is a
self-contained subject the route itself doesn't need to know the details of.
"""

from __future__ import annotations

from fastapi import status

from voxtrama.api.errors import ProblemException


class RangeUnsatisfiable(Exception):
    """A syntactically valid Range falls entirely outside the file."""


def _parse_range_header(range_header: str) -> tuple[str, str] | None:
    """Split a single-range `Range: bytes=a-b` header into its two halves.

    Only syntax is checked here. Whether the numbers make sense for the
    file is `_bounds_for_range`'s job, once it knows the file's size.
    Returns None for anything unsupported: a multi-range request, or a
    header that isn't the `bytes=` form at all.
    """
    if "," in range_header or not range_header.startswith("bytes="):
        return None

    spec = range_header[len("bytes=") :]
    start_str, sep, end_str = spec.partition("-")
    if not sep or (start_str == "" and end_str == ""):
        return None
    return start_str, end_str


def _bounds_for_range(start_str: str, end_str: str, file_size: int) -> tuple[int, int] | None:
    """Turn the two halves of a Range spec into a concrete inclusive (start, end).

    Raises RangeUnsatisfiable when the range names bytes the file does not
    have. Returns None when the numbers themselves don't parse, which the
    caller treats the same as a header it could not read at all.
    """
    try:
        if start_str == "":
            # bytes=-n: the last n bytes of the file.
            suffix_length = int(end_str)
            if suffix_length <= 0:
                return None
            start, end = max(file_size - suffix_length, 0), file_size - 1
        elif end_str == "":
            # bytes=a-: from position a to the end.
            start, end = int(start_str), file_size - 1
        else:
            start, end = int(start_str), int(end_str)
    except ValueError:
        return None

    if start < 0 or end < start:
        return None
    if start >= file_size:
        raise RangeUnsatisfiable
    return start, min(end, file_size - 1)


def resolve_range(range_header: str | None, file_size: int) -> tuple[int, int, bool]:
    """Decide what to serve: the parsed range, or the whole file if there is none.

    A missing, malformed, or multi-range header falls back to the whole
    file rather than an error, per RFC 9110. The third element of the
    result says whether a range was honoured. Raises
    RangeUnsatisfiable when the header is well-formed but names bytes the
    file does not have.
    """
    if range_header is not None:
        parsed = _parse_range_header(range_header)
        if parsed is not None:
            bounds = _bounds_for_range(*parsed, file_size)
            if bounds is not None:
                return bounds[0], bounds[1], True
    return 0, file_size - 1, False


def range_not_satisfiable(file_size: int) -> ProblemException:
    """Build the 416 for a Range that names bytes the file does not have.

    Content-Range carries the file's actual size (RFC 9110) even on the
    error, so a client that asked for the wrong offset learns the right one.
    """
    return ProblemException(
        status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
        code="range_not_satisfiable",
        title="The requested range cannot be satisfied",
        detail=f"the file is {file_size} bytes",
        headers={"Content-Range": f"bytes */{file_size}"},
    )
