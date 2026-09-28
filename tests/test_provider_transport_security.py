"""How a credential travels to a model server.

Three gaps, each measured:

- a credential went over plain http to a remote server, where Basic is
  only base64;
- urllib follows a redirect and copies Authorization onto it, whatever the
  new host or scheme;
- `https://user:secret@host` in the address was shown on two pages, copied
  into voxtrama.toml, and crashed with the secret in the message.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pydantic import ValidationError

from voxtrama.config.providers import ProviderConfig
from voxtrama.config.settings import Settings
from voxtrama.providers.base import ProviderTransportError
from voxtrama.providers.http import get_json
from voxtrama.providers.ollama import auth_header


def test_a_credential_never_goes_over_plain_http_to_a_remote_server() -> None:
    with pytest.raises(ProviderTransportError, match="only sent over https"):
        auth_header("user:secret", "http://gpu.example.org:11434")


@pytest.mark.parametrize(
    "url",
    ["https://gpu.example.org", "http://localhost:11434", "http://host.docker.internal:11434"],
)
def test_https_or_a_local_server_gets_the_credential(url: str) -> None:
    assert auth_header("token", url) == {"Authorization": "Bearer token"}


def test_no_credential_means_no_header_whatever_the_scheme() -> None:
    assert auth_header(None, "http://gpu.example.org") == {}


class _Recorder(BaseHTTPRequestHandler):
    seen: list[tuple[str, str | None]] = []
    target = ""

    def do_GET(self) -> None:
        _Recorder.seen.append((self.path, self.headers.get("Authorization")))
        if self.path == "/api/tags":
            self.send_response(302)
            self.send_header("Location", f"{_Recorder.target}/elsewhere")
        else:
            self.send_response(200)
        self.end_headers()

    def log_message(self, *args) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    _Recorder.seen, _Recorder.target = [], url
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield url
    httpd.shutdown()


def test_a_redirect_is_not_followed_with_the_credential(server: str) -> None:
    response = get_json(f"{server}/api/tags", {"Authorization": "Bearer secret"}, timeout=5)

    assert response.status == 302
    assert _Recorder.seen == [("/api/tags", "Bearer secret")]


def test_an_address_urllib_cannot_read_fails_without_the_secret() -> None:
    with pytest.raises(ProviderTransportError) as caught:
        get_json("http://user:s3cret@example.invalid/api/tags", {}, timeout=5)

    assert "s3cret" not in str(caught.value)


@pytest.mark.parametrize(
    "url", ["https://user:s3cret@gpu.example.org", "https://tok@gpu.example.org"]
)
def test_a_credential_written_into_the_address_is_refused_without_repeating_it(url: str) -> None:
    for build in (lambda: Settings(ollama_url=url), lambda: ProviderConfig(url=url)):
        with pytest.raises(ValidationError) as caught:
            build()
        assert "s3cret" not in str(caught.value)
        assert "tok@" not in str(caught.value)
        assert "auth" in str(caught.value)
