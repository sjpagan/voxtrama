"""Building an /api/generate payload, and parsing what Ollama sends back.

Split out of ollama.py to keep OllamaProvider.generate() thin. This is the
context-budget half of the contract (options and the two truncation signals),
kept apart from the provider half (host, credentials, provenance) that
ollama.py still owns.

StreamAccumulator is the other half of `"stream": true`. It folds
the NDJSON lines from http_stream.post_json_streaming, one at a time,
back into the shape a `"stream": false` body had, so parse_generation
below reads both the same way.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from voxtrama.providers.base import GenerationResult, ProviderResponseError


def build_generate_payload(
    model: str, prompt: str, json_output: bool, options: dict[str, Any] | None
) -> dict[str, Any]:
    """The /api/generate body: `options` forwarded as given, never a default here."""
    # "stream": True keeps the run page's terminal panel updating:
    # Ollama answers one JSON object per line as the text is produced, and
    # providers.http_stream feeds each to StreamAccumulator. With False the
    # code still runs and the tests still pass (the fake transport replays
    # NDJSON regardless), but a real call arrives in one piece and the panel
    # stays silent for the whole generation.
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": True}
    if options:
        payload["options"] = options
    if json_output:
        # Measured on a thinking-capable model: format alone
        # (thinking left on) returns an empty response, because the model
        # spends its budget reasoning. think alone (format left off) leaves
        # that reasoning inside response, corrupting the JSON.
        # They always go together.
        payload["format"] = "json"
        payload["think"] = False
    return payload


def parse_generation(body: dict[str, Any], host: str) -> GenerationResult:
    """`response` plus the two truncation fields, each read as None if absent or the wrong type.

    Only a missing `response` is a hard failure: without it generate() has
    nothing to return. A missing `done_reason` or `prompt_eval_count` (an
    older Ollama, or a body that never got that far) leaves the caller
    with less to check, and does not fail the call.
    """
    text = body.get("response")
    if not isinstance(text, str):
        raise ProviderResponseError(f"{host}: response has no usable 'response' field")
    done_reason = body.get("done_reason")
    prompt_eval_count = body.get("prompt_eval_count")
    return GenerationResult(
        text=text,
        done_reason=done_reason if isinstance(done_reason, str) else None,
        prompt_eval_count=prompt_eval_count if isinstance(prompt_eval_count, int) else None,
    )


@dataclass
class StreamAccumulator:
    """Folds /api/generate's NDJSON lines into one non-streaming-shaped body.

    Each line is a small JSON object. `response` carries one fragment of
    text, and only the last line (`done: true`) also carries `done_reason`
    and `prompt_eval_count`. `merged_body` reattaches every fragment to
    that last line, so it reads like the body `"stream": false` returned.
    """

    host: str
    chars_generated: int = 0
    _fragments: list[str] = field(default_factory=list)
    _last_line: dict[str, Any] | None = None

    def add_line(self, raw: bytes) -> None:
        """Parse one NDJSON line and fold its response fragment in."""
        try:
            line = json.loads(raw)
        except json.JSONDecodeError as exc:
            msg = f"{self.host}: streamed response carried a bad line"
            raise ProviderResponseError(msg) from exc
        fragment = line.get("response")
        if isinstance(fragment, str):
            self._fragments.append(fragment)
            self.chars_generated += len(fragment)
        self._last_line = line

    def merged_body(self) -> dict[str, Any]:
        """The last line's fields, with `response` replaced by all fragments joined."""
        if self._last_line is None:
            raise ProviderResponseError(f"{self.host}: streamed response carried no lines")
        merged = dict(self._last_line)
        merged["response"] = "".join(self._fragments)
        return merged
