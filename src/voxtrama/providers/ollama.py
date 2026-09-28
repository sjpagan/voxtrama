"""Ollama over HTTP: one call, its provenance, and the header a secret picks.

The generative side has one provider today. The Protocol in
providers/base.py exists so a second one would never have to touch the
engine. A second one is not expected soon.

generate() reads `"stream": true` (ollama_generation.build_generate_payload)
one NDJSON line at a time (providers.http_stream). StreamAccumulator
folds the fragments back into one body so parse_generation reads it as
before, and ollama_call_log.progress_logger turns the fragments arriving
in between into an advancing line in the terminal panel, which generative
steps did not have before.
"""

from __future__ import annotations

import base64
import time
from typing import Any
from urllib.parse import urlparse

from voxtrama.providers.base import (
    GenerationResult,
    ModelProvenance,
    ProviderCredentialsError,
    ProviderModelNotFoundError,
    ProviderResponseError,
    ProviderTransportError,
)
from voxtrama.providers.http import HttpResponse
from voxtrama.providers.http_stream import post_json_streaming
from voxtrama.providers.ollama_call_log import log_call_done, log_call_started, progress_logger
from voxtrama.providers.ollama_fingerprint import fingerprint_for
from voxtrama.providers.ollama_generation import (
    StreamAccumulator,
    build_generate_payload,
    parse_generation,
)
from voxtrama.providers.ollama_probe import GENERATE_PATH, measure_ollama_generation, probe_ollama
from voxtrama.providers.probe import GenerationSpeed, ProviderProbe

TRUNCATED_BODY_LENGTH = 200

# This worker runs inside a container, and host.docker.internal is, by
# Docker's design, the name of the machine hosting it. It counts as local,
# or local_only would be unusable in the only way this product ships today.
# If someone remaps that name the classification is wrong.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def classify_host(url: str) -> tuple[str, bool]:
    """The stripped host of `url`, and whether it counts as local.

    `urlparse` discards a `user:pass@host` userinfo on its own, so a
    credential embedded in ollama_url never reaches the value returned here.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return host, parsed.hostname in LOCAL_HOSTS


def auth_header(auth: str | None, url: str) -> dict[str, str]:
    """Authorization for `auth`: Basic if it carries a `:`, Bearer otherwise.

    Public: setup.generative_step sends it too. Refused over plain
    http to a remote host: Basic is only base64,
    and anyone on the network in between would read it. A local host never
    leaves the machine, so http is fine there.
    """
    if auth is None:
        return {}
    host, is_local = classify_host(url)
    if urlparse(url).scheme != "https" and not is_local:
        raise ProviderTransportError(
            f"{host}: credentials are only sent over https to a remote server"
        )
    if ":" in auth:
        encoded = base64.b64encode(auth.encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {encoded}"}
    return {"Authorization": f"Bearer {auth}"}


def _raise_for_status(response: HttpResponse, host: str, model: str) -> None:
    """Table 3 of the specification: a type per condition, never a parsed body."""
    if response.status == 200:
        return
    if response.status in (401, 403):
        raise ProviderCredentialsError(f"{host} requires credentials we do not have")
    if response.status == 404:
        raise ProviderModelNotFoundError(f"{host} has no model '{model}'")
    snippet = response.body[:TRUNCATED_BODY_LENGTH].decode("utf-8", errors="replace")
    raise ProviderResponseError(f"{host} answered {response.status}: {snippet}")


class OllamaProvider:
    """A TextProvider backed by one Ollama server, at `url`."""

    def __init__(self, url: str, auth: str | None, timeout: float) -> None:
        self._url = url.rstrip("/")
        self._auth = auth
        self._timeout = timeout
        self._host, self._is_local = classify_host(url)

    def generate(
        self,
        prompt: str,
        model: str,
        json_output: bool = False,
        *,
        options: dict[str, Any] | None = None,
    ) -> tuple[GenerationResult, ModelProvenance]:
        headers = auth_header(self._auth, self._url)
        payload = build_generate_payload(model, prompt, json_output, options)
        log_call_started(model, prompt, options)
        started = time.monotonic()
        accumulator = StreamAccumulator(self._host)
        report_progress = progress_logger(model)

        def on_line(raw: bytes) -> None:
            accumulator.add_line(raw)
            report_progress(accumulator.chars_generated)

        response = post_json_streaming(
            f"{self._url}{GENERATE_PATH}", payload, headers, self._timeout, on_line
        )
        _raise_for_status(response, self._host, model)
        result = parse_generation(accumulator.merged_body(), self._host)
        log_call_done(model, result, round((time.monotonic() - started) * 1000))
        provenance = ModelProvenance(
            provider="ollama",
            host=self._host,
            model=model,
            fingerprint=fingerprint_for(self._url, self._host, model, headers, self._timeout),
            remote=not self._is_local,
            profile_check_skipped=not self._is_local,
        )
        return result, provenance

    def probe(self) -> ProviderProbe:
        return probe_ollama(
            self._url, self._host, auth_header(self._auth, self._url), self._timeout
        )

    def measure_generation(self, model: str) -> GenerationSpeed:
        headers = auth_header(self._auth, self._url)
        return measure_ollama_generation(self._url, self._host, model, headers, self._timeout)
