"""Who may talk to the app, and what a page may do once loaded.

Voxtrama has no login: it listens on 127.0.0.1 only, and that address was
taken as the whole boundary. It is not one. Any website open in the same
browser can send requests to 127.0.0.1:8000:

- a form or a `fetch(..., {mode: "no-cors"})` POST from another site was
  accepted, so a page could create jobs, change the retention and then run
  the clean-up that deletes them;
- with DNS rebinding, a site's own name resolves to 127.0.0.1 and the
  browser treats the app as that site: it could read every transcript.

So, on every request:

- the Host must be one of Settings.allowed_hosts, which ends DNS
  rebinding (the rebound request still carries the attacker's name);
- a request that changes something (anything but GET, HEAD, OPTIONS) must
  come from the app's own pages: its Origin, when sent, must be the Host
  it was sent to, and `Sec-Fetch-Site`, when sent, must say so too.

And on every response, headers that keep a page from being framed (the
delete buttons under an invisible iframe), limit scripts to the app's own
files, and stop a browser from reading a file as another type.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from voxtrama.config.settings import get_settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# style-src keeps 'unsafe-inline' for a few style="" attributes in the
# templates; scripts get no such allowance, and the app has no inline one.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; media-src 'self'; object-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
SECURITY_HEADERS = [
    (b"content-security-policy", CONTENT_SECURITY_POLICY.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    # same-origin, not no-referrer: with no-referrer Chrome sends "Origin: null"
    # on the app's own form posts, and they would be refused as cross-site.
    (b"referrer-policy", b"same-origin"),
]


def _headers(scope: Scope) -> dict[str, str]:
    return {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}


def host_name(host: str) -> str:
    """`host` without its port, brackets removed from an IPv6 address."""
    return (urlsplit(f"//{host}").hostname or "").lower()


def refusal(scope: Scope) -> str | None:
    """Why this request is refused, or None when it may go on."""
    headers = _headers(scope)
    host = headers.get("host", "")
    if host_name(host) not in {name.lower() for name in get_settings().allowed_hosts}:
        return "unknown host"
    if scope["method"] in SAFE_METHODS:
        return None
    origin = headers.get("origin")
    if origin is not None and urlsplit(origin).netloc.lower() != host.lower():
        return "cross-site request"
    if headers.get("sec-fetch-site", "same-origin") not in {"same-origin", "none"}:
        return "cross-site request"
    return None


class SecurityMiddleware:
    """Refuse what `refusal` names with a 403, and add SECURITY_HEADERS to the rest."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        reason = refusal(scope)
        if reason is not None:
            await _forbidden(send, reason)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                own = {name.lower() for name, _ in headers}  # a route's own value wins
                headers += [pair for pair in SECURITY_HEADERS if pair[0] not in own]
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _forbidden(send: Send, reason: str) -> None:
    body = f"Forbidden: {reason}.".encode()
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
                *SECURITY_HEADERS,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
