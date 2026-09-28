"""Reading a model's context ceiling and licence text from Ollama's
/api/show: `<architecture>.context_length` and the `license` field, both
from the same response.

262144 for qwen3 and 131072 for gemma3 are the context_length values
measured. The licence field carries the model's own text, e.g.
"Apache License / Version 2.0, ..." for qwen3. One POST, mirroring
ollama_probe.py's request shape (Ollama's /api/show contract, unlike the
GETs probe_ollama makes), never raising. A caller that cannot get either
field (the model is not installed, the host does not answer) reads both
as "unknown" without catching anything and never
asks twice for what one request already carries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from voxtrama.providers.base import ProviderError
from voxtrama.providers.http import parse_json_body, post_json

SHOW_PATH = "/api/show"


@dataclass(frozen=True)
class ModelFacts:
    """What one /api/show read gives about a model: its num_ctx ceiling
    and the licence text it declares. Either or both is None when the read
    failed or the field was absent, never a placeholder standing in for a
    value that was never there.
    """

    context_length: int | None
    licence_text: str | None


def read_model_facts(
    url: str, host: str, model: str, headers: dict[str, str], timeout: float
) -> ModelFacts:
    """`model`'s context_length and licence text, read together.

    Never raises. A caller treats this like every other diagnostics
    reading: a value that could not be read is unknown, not a fault the
    request should fail over.
    """
    try:
        response = post_json(f"{url}{SHOW_PATH}", {"model": model}, headers, timeout)
        if response.status != 200:
            return ModelFacts(context_length=None, licence_text=None)
        body = parse_json_body(response, host)
    except ProviderError:
        return ModelFacts(context_length=None, licence_text=None)
    return ModelFacts(context_length=_context_length(body), licence_text=_licence_text(body))


def _context_length(body: dict[str, Any]) -> int | None:
    info = body.get("model_info")
    if not isinstance(info, dict):
        return None
    architecture = info.get("general.architecture")
    if not isinstance(architecture, str):
        return None
    value = info.get(f"{architecture}.context_length")
    return value if isinstance(value, int) else None


def _licence_text(body: dict[str, Any]) -> str | None:
    text = body.get("license")
    return text if isinstance(text, str) and text.strip() else None
