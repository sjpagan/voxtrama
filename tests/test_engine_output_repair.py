"""A window's good points survive a few malformed ones."""

from __future__ import annotations

import json
import logging

import pytest

from voxtrama.engine.generation_resume import ResumedGeneration
from voxtrama.engine.output_repair import repair_output
from voxtrama.engine.window_outputs import window_outputs
from voxtrama.providers.base import ModelProvenance

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "key_points"],
    "properties": {
        "summary": {"type": "string"},
        "key_points": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "quote"],
                "properties": {"text": {"type": "string"}, "quote": {"type": "string"}},
            },
        },
    },
}
GOOD = {"text": "a", "quote": "q"}
PROVENANCE = ModelProvenance("ollama", "127.0.0.1", "m", None, False, False)


def test_a_stray_field_and_malformed_points_are_dropped(caplog) -> None:
    output = {"summary": "s", "quote": "stray", "key_points": [GOOD, {"text": "no quote"}]}

    with caplog.at_level(logging.WARNING):
        repaired = repair_output(output, SCHEMA, "Window 3")

    assert repaired == {"summary": "s", "key_points": [GOOD]}
    assert "Window 3: dropped" in caplog.text
    assert "field 'quote'" in caplog.text and "1 of 2 key_points" in caplog.text


def test_a_well_formed_answer_is_left_alone(caplog) -> None:
    output = {"summary": "s", "key_points": [GOOD]}

    with caplog.at_level(logging.WARNING):
        assert repair_output(dict(output), SCHEMA) == output

    assert caplog.text == ""


def test_a_missing_required_list_is_not_invented() -> None:
    assert repair_output({"summary": "s"}, SCHEMA) == {"summary": "s"}


def _gen(value: object) -> ResumedGeneration:
    text = value if isinstance(value, str) else json.dumps(value)
    return ResumedGeneration(text, PROVENANCE, 0)


def test_an_answer_still_wrong_after_trimming_is_forgotten() -> None:
    forgotten: list[int] = []

    outputs = window_outputs(
        [_gen({"summary": "s", "key_points": [GOOD]}), _gen({"summary": "s"})],
        SCHEMA,
        forgotten.append,
    )

    assert forgotten == [1]
    assert outputs[0]["key_points"] == [GOOD]


def test_an_answer_that_is_not_json_is_forgotten_and_still_fails() -> None:
    forgotten: list[int] = []

    with pytest.raises(ValueError):
        window_outputs([_gen("not json")], SCHEMA, forgotten.append)

    assert forgotten == [0]
