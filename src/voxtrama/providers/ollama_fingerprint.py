"""OllamaProvider._fingerprint's /api/tags lookup, split out for the file size limit.

The /api/generate response carries no digest field (unverified against a
live Ollama, see the commit message that first added this), so a
fingerprint costs a second call, to /api/tags, made here instead of
inline in ollama.py's generate().
"""

from __future__ import annotations

from voxtrama.providers.base import ProviderError
from voxtrama.providers.http import get_json, parse_json_body
from voxtrama.providers.ollama_probe import TAGS_PATH


def fingerprint_for(
    url: str, host: str, model: str, headers: dict[str, str], timeout: float
) -> str | None:
    """The digest /api/tags reports for `model`, or None if it does not.

    Any failure here degrades to None instead of failing generate(): the
    caller already has its text, and an honestly absent fingerprint is
    wanted, never the tag standing in for it.
    """
    try:
        response = get_json(f"{url}{TAGS_PATH}", headers, timeout)
        if response.status != 200:
            return None
        body = parse_json_body(response, host)
    except ProviderError:
        return None
    for entry in body.get("models", []):
        if entry.get("model") == model or entry.get("name") == model:
            digest = entry.get("digest")
            return digest if isinstance(digest, str) else None
    return None
