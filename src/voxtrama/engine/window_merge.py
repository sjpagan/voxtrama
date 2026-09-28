"""The outputs of every window of a transcript, joined into one.

Deterministic, in Python, no call to the model. The lists
every window returned, one after the other in the order the windows come
in the recording, without the near-identical items two windows both
found. Two windows see the same lines through their bridges, so the same
point can come back twice: with the same quote, or in nearly the same
words.

Deliberately generic, like engine.reuse_adopt: every shipped skill returns
one list of items, but nothing here names a skill or a field. A list is
joined. Any other value is the first window's. The evidence is not
carried over from the windows: engine.anchoring re-anchors every quote
against the whole transcript once the step returns.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

SAME_WORDING = 0.9
_NOT_WORDING = {"quote", "evidence", "needs_review"}


def _plain(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.lower()))


def _wording(item: Any) -> str:
    if not isinstance(item, dict):
        return _plain(str(item))
    kept = [value for key, value in item.items() if key not in _NOT_WORDING]
    return _plain(" ".join(value for value in kept if isinstance(value, str)))


def _quote(item: Any) -> str:
    quote = item.get("quote") if isinstance(item, dict) else None
    return _plain(quote) if isinstance(quote, str) else ""


def _repeats(item: Any, kept: list[Any]) -> bool:
    wording, quote = _wording(item), _quote(item)
    for other in kept:
        if quote and quote == _quote(other):
            return True
        if wording and SequenceMatcher(None, wording, _wording(other)).ratio() >= SAME_WORDING:
            return True
    return False


def _join(lists: list[list[Any]]) -> list[Any]:
    kept: list[Any] = []
    for items in lists:
        kept.extend(item for item in items if not _repeats(item, kept))
    return kept


def merge_outputs(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    """One output out of every window's, in the windows' order."""
    merged: dict[str, Any] = {}
    for key in dict.fromkeys(key for output in outputs for key in output):
        values = [output[key] for output in outputs if key in output]
        if all(isinstance(value, list) for value in values):
            merged[key] = _join(values)
        else:
            merged[key] = values[0]
    return merged
