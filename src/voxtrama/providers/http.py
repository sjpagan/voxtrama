"""A JSON request over HTTP, with the status read before the body is trusted.

The standard library, not httpx: runtime dependencies are still an open
question, and a POST with a timeout is a few dozen lines `urllib.request`
already knows how to do.

The cost: `urllib` raises `HTTPError` for every 4xx and 5xx (an `HTTPError`
is also a readable response, with `.code` and `.read()`), and `URLError`
for anything that never produced a response, timeouts included. A
timed-out connection is a `URLError` whose `.reason` is a `TimeoutError`,
not a bare one. Both are mapped to this module's own exceptions here, so
nothing downstream has to recognise a urllib exception.

`_request` reads a body in one shot. `http_stream.post_json_streaming`
reads one line at a time instead, for Ollama's NDJSON shape. It lives in
its own file for the project's line limit and shares the two mapping
functions below.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, NoReturn
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request

from voxtrama.providers.base import (
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderTransportError,
)
from voxtrama.providers.http_opener import UNUSABLE_URL, urlopen


def safe_url(url: str) -> str:
    """`url` with any embedded credential removed, for messages and logs.

    A configured `https://user:secret@host/` carries its own credential,
    and the two raises below put the URL they were given into a message
    that ends up in Run.error, then in the manifest and the progress
    file. The host may appear there and the secret never, so every
    message here is built from this, not from the URL as configured.
    """
    parsed = urlparse(url)
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


@dataclass(frozen=True)
class HttpResponse:
    """A response the caller may still reject: 200 does not mean usable JSON."""

    status: int
    body: bytes


def post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
) -> HttpResponse:
    """POST `payload` as JSON to `url`, returning the response whatever its status."""
    return _request(url, "POST", json.dumps(payload).encode("utf-8"), headers, timeout)


def get_json(url: str, headers: dict[str, str], timeout: float) -> HttpResponse:
    """GET `url`, returning the response whatever its status."""
    return _request(url, "GET", None, headers, timeout)


def _request(
    url: str, method: str, data: bytes | None, headers: dict[str, str], timeout: float
) -> HttpResponse:
    """Issue one HTTP request, mapping a transport failure but never a status.

    The caller (providers.ollama) knows how to read a 4xx or 5xx for its
    own request: a 404 means something different on /api/generate than
    elsewhere. This module has no such context, so it returns the response
    intact and only raises when there is no response at all.
    """
    all_headers = {"Content-Type": "application/json", **headers}
    request = Request(url, data=data, headers=all_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return HttpResponse(status=response.status, body=response.read())
    except HTTPError as exc:
        return read_http_error(exc)
    except URLError as exc:
        raise_for_url_error(exc, url, timeout)
    except UNUSABLE_URL as exc:
        raise ProviderTransportError(f"{safe_url(url)} is not a usable address") from exc


def read_http_error(exc: HTTPError) -> HttpResponse:
    """Read an HTTPError as the response it also is (`.code` and `.read()`).

    Public because http_stream.post_json_streaming hits the same case on
    the same transport and must map it identically, without a second copy
    of this line that could drift.
    """
    return HttpResponse(status=exc.code, body=exc.read())


def raise_for_url_error(exc: URLError, url: str, timeout: float) -> NoReturn:
    """Map a transport failure (no response at all) to this module's own exceptions.

    Public for the same reason as read_http_error: http_stream shares this
    mapping rather than reimplementing it.
    """
    if isinstance(exc.reason, TimeoutError):
        raise ProviderTimeoutError(f"{safe_url(url)} did not answer within {timeout}s") from exc
    raise ProviderTransportError(f"{safe_url(url)} is unreachable: {exc.reason}") from exc


def parse_json_body(response: HttpResponse, host: str) -> Any:
    """Decode `response.body` as JSON, or raise naming the host, not the body.

    Call only once the status has been judged usable. This turns the
    "Expecting value: line 1 column 1" trap (a 401 answered in HTML) into
    a message that names what happened instead of where the parser gave up.
    """
    try:
        return json.loads(response.body)
    except json.JSONDecodeError as exc:
        msg = f"{host} did not return JSON (status {response.status})"
        raise ProviderResponseError(msg) from exc
