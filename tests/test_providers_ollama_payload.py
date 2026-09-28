"""The one line that decides whether the streaming machinery ever runs.

Its own file, not appended to test_providers_ollama_stream.py: that one was
already at 150 lines, the project's cap, and a file at the limit is extracted
from, never compressed.
"""

from __future__ import annotations

from voxtrama.providers.ollama_generation import build_generate_payload


def test_the_generate_payload_actually_asks_for_streaming() -> None:
    """Every other streaming test replays NDJSON through a fake transport,
    which does so whatever the payload said. So the whole machinery passed
    its tests while `"stream": False` kept a real Ollama answering in one
    piece, and the run page's panel sat silent for the length of each
    generation. Measured before the fix: a single log line after 18.3s,
    where the threshold implies three. This asserts the switch itself.
    """
    payload = build_generate_payload("qwen3:4b", "hello", json_output=False, options=None)

    assert payload["stream"] is True
