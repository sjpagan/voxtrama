"""A fake urlopen for voxtrama.providers.http, routed by exact URL.

Patches the one name providers.http imports urlopen under, so no test in
this suite ever opens a real socket: the transport itself is the double,
not just the provider that sits on top of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

import voxtrama.providers.http as http_module


@dataclass
class FakeResponse:
    """What a real urlopen()'s `with` block gives back: status, and a body to read."""

    status: int
    body: bytes

    def read(self) -> bytes:
        return self.body

    def readline(self) -> bytes:
        """One line at a time, NDJSON-style, for post_json_streaming's own tests.

        `self.body` doubles as the whole stream, so a routed FakeResponse
        already carries every line joined with `\\n`; this hands them back
        one at a time and an empty bytes once exhausted, like a
        real socket at EOF.
        """
        if not self.body:
            return b""
        line, _, rest = self.body.partition(b"\n")
        self.body = rest
        return line

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class FakeTransport:
    """Answers each request by URL, and records every one it was asked to make."""

    def __init__(self) -> None:
        self.calls: list[Request] = []
        self._routes: dict[str, FakeResponse | Exception] = {}

    def route(self, url: str, result: FakeResponse | Exception) -> None:
        """Have the next request to `url` return `result`, or raise it."""
        self._routes[url] = result

    def __call__(self, request: Request, timeout: float | None = None) -> FakeResponse:
        self.calls.append(request)
        if request.full_url not in self._routes:
            raise AssertionError(f"unrouted request to {request.full_url}")
        result = self._routes[request.full_url]
        if isinstance(result, Exception):
            raise result
        # A fresh copy per call: readline() consumes the body, and one
        # route may answer several calls (the context deduction asks the
        # same model before the step's own call).
        return FakeResponse(result.status, result.body)


def install(monkeypatch: pytest.MonkeyPatch) -> FakeTransport:
    """Replace providers.http's urlopen with a fresh FakeTransport, and return it."""
    transport = FakeTransport()
    monkeypatch.setattr(http_module, "urlopen", transport)
    return transport


def timeout_error() -> URLError:
    """What a real urlopen(timeout=...) raises when the provider never answers."""
    return URLError(TimeoutError("timed out"))


def http_error(code: int, body: bytes) -> HTTPError:
    """A real HTTPError carrying `body`: what urlopen raises for a 4xx/5xx.

    providers.http reads it through `.code` and `.read()`, as it would a
    genuine one, so a stand-in would not do.
    """
    return HTTPError("http://fake", code, "reason", Message(), BytesIO(body))
