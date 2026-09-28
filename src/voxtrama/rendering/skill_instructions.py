"""What a generative step tells the model, as the Workflows pages show it.

A system skill's instructions are its prompt, read-only. A custom
workflow's step can carry its own (workflow.instructions), started from
that text. The placeholders are split out so the page can mark where the
transcript, the language and the detail go. `returns` names what the
step hands back, read off the skill's output_schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from voxtrama.engine.skill_catalog import load_named_skill_file
from voxtrama.workflow.definition import Step

# Added by the engine after the model answers (engine.anchoring), not asked for.
_FILLED_IN = ("evidence", "needs_review")
_PLACEHOLDER = re.compile(r"(\{(?:transcript|language|detail)\})")


@dataclass(frozen=True)
class StepInstructions:
    """The text a step sends to the model, in pieces, and what it returns."""

    text: str
    edited: bool
    parts: tuple[tuple[str, bool], ...]  # (piece, is a placeholder)
    returns: tuple[str, ...]


def system_prompt(skill: str) -> str | None:
    """The shipped prompt of `skill`, None for a skill with no instructions to a model."""
    try:
        return load_named_skill_file(skill).prompt
    except Exception:  # a built-in (transcribe, diarize), or a file gone or broken
        return None


def _returns(schema: dict[str, Any]) -> tuple[str, ...]:
    fields = []
    for name, spec in schema.get("properties", {}).items():
        item = spec.get("items", {}) if spec.get("type") == "array" else {}
        inner = [key for key in item.get("properties", {}) if key not in _FILLED_IN]
        fields.append(f"{name} ({', '.join(inner)})" if inner else name)
    return tuple(fields)


def step_instructions(step: Step) -> StepInstructions | None:
    """What `step` tells the model, or None when it tells a model nothing."""
    shipped = system_prompt(step.skill)
    if shipped is None:
        return None
    text = step.instructions or shipped
    pieces = tuple(
        (piece, bool(_PLACEHOLDER.fullmatch(piece))) for piece in _PLACEHOLDER.split(text)
    )
    schema = load_named_skill_file(step.skill).skill.output_schema
    return StepInstructions(
        text=text,
        edited=bool(step.instructions),
        parts=tuple(piece for piece in pieces if piece[0]),
        returns=_returns(schema),
    )
