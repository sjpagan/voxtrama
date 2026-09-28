"""A JSON POST read one line at a time, for Ollama's own NDJSON shape.

Split out of http.py to keep that file under the project's line limit.
This is the incremental sibling of `_request`'s one-shot `.read()`, added
next to it. `post_json` and `get_json` still read a body whole, and their
callers (ollama_probe.py, ollama_show.py) are unaffected by this file.

Calls `http.urlopen` through the module, not via its own `from ... import
urlopen`: tests patch `voxtrama.providers.http.urlopen` (fakes.http_transport
.install), and a separate binding here would escape that patch. One fake
transport has to cover both ways of reading a response.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

from voxtrama.providers import http
from voxtrama.providers.base import ProviderTransportError
from voxtrama.providers.http import (
    UNUSABLE_URL,
    HttpResponse,
    raise_for_url_error,
    read_http_error,
    safe_url,
)


def post_json_streaming(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
    on_line: Callable[[bytes], None],
) -> HttpResponse:
    """POST `payload`, calling `on_line` once per line of a 200 response's body.

    Ollama's `"stream": true` shape (ollama_generation.build_generate_payload)
    answers with one JSON object per line instead of one body at the end.
    `on_line` lets the caller (providers.ollama, which knows what a
    "response" fragment is) parse and accumulate them as they arrive, so
    this module knows nothing about their shape.

    Only a 200 is read line by line. A 4xx/5xx is never NDJSON in Ollama's
    contract, and `_raise_for_status` needs the whole body anyway, so
    anything else falls back to the single `.read()` `_request` uses.

    `timeout` keeps its old meaning at the socket level, not for the whole
    request: it is set once, on `urlopen`, and the standard library resets
    that countdown on every read. A one-shot `.read()` already waited out
    the entire generation in one such wait. Reading line by line only moves
    *where* the waiting happens (between two lines instead of before the
    only one), so a slow but live model is less likely to trip it than
    before.
    """
    all_headers = {"Content-Type": "application/json", **headers}
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=all_headers, method="POST")
    try:
        with http.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return HttpResponse(status=response.status, body=response.read())
            while raw_line := response.readline():
                line = raw_line.strip()
                if line:
                    on_line(line)
            return HttpResponse(status=200, body=b"")
    except HTTPError as exc:
        return read_http_error(exc)
    except URLError as exc:
        raise_for_url_error(exc, url, timeout)
    except UNUSABLE_URL as exc:
        raise ProviderTransportError(f"{safe_url(url)} is not a usable address") from exc
