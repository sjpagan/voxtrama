"""Each window's answer read, trimmed, and forgotten when it cannot be used.

engine.window_cache keeps every answer so a retry does not ask again. An
answer that is not JSON, or still does not match the skill's schema after
engine.output_repair has trimmed it, must not be kept: the retry would
find it and fail the same way forever. So such an answer is dropped from
the cache here, and the step goes on to fail exactly as before
(engine.validation), leaving the retry free to ask that window again.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

from jsonschema import Draft202012Validator

from voxtrama.engine.generation_resume import ResumedGeneration
from voxtrama.engine.output_repair import repair_output


def window_outputs(
    generations: Sequence[ResumedGeneration],
    schema: dict[str, Any],
    forget: Callable[[int], None],
) -> list[Any]:
    """The parsed, trimmed answers in window order; `forget(index)` for each unusable one."""
    validator = Draft202012Validator(schema)
    outputs: list[Any] = []
    for index, generation in enumerate(generations):
        try:
            output = json.loads(generation.text)
        except ValueError:
            forget(index)
            raise
        output = repair_output(output, schema, f"Window {index + 1}")
        if not validator.is_valid(output):
            forget(index)
        outputs.append(output)
    return outputs
