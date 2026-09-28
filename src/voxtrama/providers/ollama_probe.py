"""Reachability, version and generation speed for one Ollama server.

Split from ollama.py by context, not by size (the project's 150-line file limit).
generate() is the engine's path, called on every step. These are doctor's
path, called once, by a person. ollama.py imports the path constants and
functions here, not the reverse: this module knows nothing about
OllamaProvider.
"""

from __future__ import annotations

import time
from typing import Any

from voxtrama.providers.base import ProviderError, ProviderResponseError
from voxtrama.providers.http import get_json, parse_json_body, post_json
from voxtrama.providers.probe import GenerationSpeed, ProviderModel, ProviderProbe

GENERATE_PATH = "/api/generate"
TAGS_PATH = "/api/tags"
VERSION_PATH = "/api/version"

# Kept short: measuring costs real seconds, and a short
# prompt keeps eval_count small so the timing is quick.
SPEED_PROMPT = "Reply with one word: ready."


def probe_ollama(url: str, host: str, headers: dict[str, str], timeout: float) -> ProviderProbe:
    """Time /api/version (the cheapest call), then read what /api/tags adds.

    Never raises: every ProviderError either endpoint can produce is caught
    and turned into reachable=False with a readable `error`, per the
    TextProvider.probe() contract.
    """
    start = time.monotonic()
    try:
        response = get_json(f"{url}{VERSION_PATH}", headers, timeout)
    except ProviderError as exc:
        return ProviderProbe(
            reachable=False, latency_seconds=None, version=None, models=(), error=str(exc)
        )
    latency = time.monotonic() - start
    if response.status != 200:
        error = f"{host} answered {response.status} to {VERSION_PATH}"
        return ProviderProbe(
            reachable=False, latency_seconds=latency, version=None, models=(), error=error
        )
    body = parse_json_body(response, host)
    version = body.get("version") if isinstance(body.get("version"), str) else None
    models = _read_models(url, host, headers, timeout)
    return ProviderProbe(
        reachable=True, latency_seconds=latency, version=version, models=models, error=None
    )


def _read_models(
    url: str, host: str, headers: dict[str, str], timeout: float
) -> tuple[ProviderModel, ...]:
    """The models /api/tags reports, or empty if that second call fails.

    A working /api/version already earned "reachable": failing here only
    means doctor has nothing to say about which models are present.
    """
    try:
        response = get_json(f"{url}{TAGS_PATH}", headers, timeout)
        if response.status != 200:
            return ()
        body = parse_json_body(response, host)
    except ProviderError:
        return ()
    models = []
    for entry in body.get("models", []):
        name = entry.get("name") or entry.get("model")
        if not isinstance(name, str):
            continue
        size = entry.get("size")
        models.append(ProviderModel(name=name, size_bytes=size if isinstance(size, int) else None))
    return tuple(models)


def measure_ollama_generation(
    url: str, host: str, model: str, headers: dict[str, str], timeout: float
) -> GenerationSpeed:
    """Time one short generation on `model`, shaped like a real run's.

    engine/generative.py only calls generate(json_output=True), which sets
    `format: json` and `think: false` *together*. It was measured that
    either one alone breaks a thinking-capable model, and
    test_engine_summarize_prompt asserts the pair. Sending one of them here
    would time a request no run ever makes: measured on qwen3:4b, `think`
    alone let the model answer a one-word prompt with 123 tokens, against
    86 for the pair. The number would still be a rate, but of the wrong
    request. Raises ProviderError on a bad status or transport failure:
    unlike probe(), doctor's caller decides how to report that (see
    base.TextProvider).
    """
    payload: dict[str, Any] = {
        "model": model,
        "prompt": SPEED_PROMPT,
        "stream": False,
        "format": "json",
        "think": False,
    }
    start = time.monotonic()
    response = post_json(f"{url}{GENERATE_PATH}", payload, headers, timeout)
    wall_seconds = time.monotonic() - start
    if response.status != 200:
        raise ProviderResponseError(f"{host} answered {response.status} measuring generation speed")
    body = parse_json_body(response, host)
    return _speed_from_body(model, body, wall_seconds)


def _speed_from_body(model: str, body: dict[str, Any], wall_seconds: float) -> GenerationSpeed:
    """GenerationSpeed from one /api/generate body: provider timings first, never invented."""
    eval_count, eval_duration = body.get("eval_count"), body.get("eval_duration")
    if isinstance(eval_count, int) and isinstance(eval_duration, int) and eval_duration > 0:
        tokens, tokens_per_second, source = (
            eval_count,
            eval_count / (eval_duration / 1e9),
            "provider timings",
        )
    else:
        tokens, tokens_per_second, source = None, None, "wall clock"
    load_duration = body.get("load_duration")
    load_seconds = load_duration / 1e9 if isinstance(load_duration, int) else None
    return GenerationSpeed(
        model=model,
        tokens=tokens,
        tokens_per_second=tokens_per_second,
        load_seconds=load_seconds,
        wall_seconds=wall_seconds,
        source=source,
    )
