"""engine.generation_resume: resuming past an output cap, refusing a truncated input.

TextProvider is a Protocol, so a plain stub returning canned
GenerationResults *is* the provider here: no HTTP, no fakes.
http_transport, because this module's own policy (when to resume, when
to give up) has nothing to do with how a response reached it.
"""

from __future__ import annotations

import pytest

from voxtrama.engine.context_budget import ContextBudget
from voxtrama.engine.generation_resume import (
    GenerationTruncatedError,
    PromptTruncatedError,
    generate_with_resume,
)
from voxtrama.providers.base import GenerationResult, ModelProvenance

_PROVENANCE = ModelProvenance(
    provider="ollama",
    host="127.0.0.1:11434",
    model="m",
    fingerprint=None,
    remote=False,
    profile_check_skipped=False,
)


class _StubProvider:
    """Hands back each of `responses` in turn, and records every call it was asked to make."""

    def __init__(self, responses: list[GenerationResult]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, bool, dict | None]] = []

    def generate(self, prompt, model, json_output=False, *, options=None):
        self.calls.append((prompt, json_output, options))
        return self._responses.pop(0), _PROVENANCE


def _budget(estimated: int = 100, num_ctx: int = 4096) -> ContextBudget:
    return ContextBudget(num_ctx=num_ctx, estimated_prompt_tokens=estimated, at_risk=False)


def test_a_clean_generation_needs_no_resumption():
    provider = _StubProvider([GenerationResult("done", "stop", 100)])

    generation = generate_with_resume(provider, "prompt", "m", _budget())

    assert generation.text == "done"
    assert generation.resumptions == 0
    assert len(provider.calls) == 1


def test_a_truncated_output_is_resumed_once_and_then_completes():
    provider = _StubProvider(
        [
            GenerationResult("part one ", "length", 100),
            GenerationResult("part two", "stop", None),
        ]
    )

    generation = generate_with_resume(provider, "prompt", "m", _budget())

    assert generation.text == "part one part two"
    assert generation.resumptions == 1
    _, json_output, options = provider.calls[1]
    assert json_output is False  # never asks the continuation to restart as JSON
    assert options == {"num_ctx": _budget().num_ctx}  # same window, reused unchanged


def test_still_truncated_after_max_resumptions_fails():
    provider = _StubProvider(
        [
            GenerationResult("a", "length", 100),
            GenerationResult("b", "length", None),
            GenerationResult("c", "length", None),
        ]
    )

    with pytest.raises(GenerationTruncatedError):
        generate_with_resume(provider, "prompt", "m", _budget())

    assert len(provider.calls) == 3  # the first call, plus exactly two resumptions


def test_a_prompt_read_only_partially_fails_before_any_resumption_is_tried():
    """The field measurement: prompt_eval_count at the num_ctx
    requested (the default, unset, 2048) proves the cut, never a
    comparison against the (deliberately oversized) token estimate.
    """
    provider = _StubProvider([GenerationResult("whatever", "stop", 2050)])
    budget = _budget(estimated=10_296, num_ctx=2048)

    with pytest.raises(PromptTruncatedError):
        generate_with_resume(provider, "prompt", "m", budget)

    assert len(provider.calls) == 1  # never even tries to resume a broken read
