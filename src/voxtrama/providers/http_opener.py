"""The opener every provider request goes through.

Split from http.py for the project's line limit. http.py imports `urlopen`
from here under its own name, which is the one tests patch
(fakes.http_transport).
"""

from __future__ import annotations

from http.client import HTTPException
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    """Never follow a redirect: the 3xx comes back as the response it is.

    urllib's own handler copies every header, Authorization included, onto
    the redirected request, whatever its host or scheme. A server answering 302 to
    http://elsewhere/ would get the credential in clear. Ollama never redirects, so nothing is lost.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(_NoRedirect)


def urlopen(request: Request, timeout: float):
    """Open `request` without following redirects. Tests patch this name."""
    return _OPENER.open(request, timeout=timeout)


# A URL urllib cannot even parse (`http://user:secret@host/` reads the
# secret as a port) raises these, not URLError: mapped the same way, so the
# URL as written never reaches a message.
UNUSABLE_URL = (ValueError, HTTPException)
