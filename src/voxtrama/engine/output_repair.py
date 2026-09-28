"""A window's answer keeps its good points when a few are malformed.

A real job failed its whole recap after 29 minutes of transcription:
qwen3:4b wrote one window with a stray "quote" at the top level and two
key points without a proper quote. engine.validation then rejected the
step, and every well-formed point of the other windows went with it.

Before the windows are joined, each answer is trimmed to the shape the
skill declares: a top-level field the schema does not know is dropped, and
so is an item of a list that does not match the list's item schema. What
was dropped is logged. Whatever is left still goes through
engine.validation unchanged, so a window whose answer is entirely wrong
(a missing required list, a scalar where a list belongs) fails the step
exactly as before.
"""

from __future__ import annotations

import logging
from typing import Any

from jsonschema import Draft202012Validator

logger = logging.getLogger(__name__)


def repair_output(output: Any, schema: dict[str, Any], label: str = "") -> Any:
    """`output` without unknown top-level fields and without malformed list items."""
    if not isinstance(output, dict):
        return output
    properties: dict[str, Any] = schema.get("properties", {})
    dropped: list[str] = []
    if schema.get("additionalProperties") is False:
        for key in [k for k in output if k not in properties]:
            output.pop(key)
            dropped.append(f"field '{key}'")
    for key, value in output.items():
        items = properties.get(key, {}).get("items")
        if isinstance(value, list) and isinstance(items, dict):
            validator = Draft202012Validator(items)
            kept = [item for item in value if validator.is_valid(item)]
            if len(kept) < len(value):
                dropped.append(f"{len(value) - len(kept)} of {len(value)} {key}")
            output[key] = kept
    if dropped:
        prefix = f"{label}: " if label else ""
        logger.warning(
            "%sdropped what did not match the expected shape: %s", prefix, ", ".join(dropped)
        )
    return output
