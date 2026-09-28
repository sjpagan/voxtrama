"""Calls a TextProvider until it can honestly be called done.

Two different failures live here. An input truncation is proven
the moment the first call returns. Ollama's done_reason says nothing about
it, so nothing is worth resuming. An output truncation
(done_reason == "length") is something Ollama does report, and gets up to
MAX_RESUMPTIONS chances before the step gives up. One exception for both
would lose that distinction.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.engine.context_budget import ContextBudget, prompt_was_truncated
from voxtrama.providers.base import ModelProvenance, TextProvider

# The resumption numbers, taken as-is from their formula.
CONTINUATION_TAIL_CHARS = 800
MAX_RESUMPTIONS = 2
LENGTH_DONE_REASON = "length"


class PromptTruncatedError(RuntimeError):
    """prompt_eval_count says the model read only a fraction of the prompt.

    Raised instead of returning the model's answer as though it had read
    the whole thing, the one guarantee this module exists to give back.
    """


class GenerationTruncatedError(RuntimeError):
    """Ollama still hit its output cap after MAX_RESUMPTIONS continuations."""


@dataclass(frozen=True)
class ResumedGeneration:
    """What a (possibly resumed) generation produced, and how many times it had to resume."""

    text: str
    provenance: ModelProvenance
    resumptions: int


def _continuation_prompt(tail: str) -> str:
    """Ask the model to pick up exactly where `tail` stops."""
    return (
        "Continue the text below exactly where it stops. Do not repeat "
        "any part of it and do not start over. Write only what comes "
        f"next.\n\n{tail}"
    )


def generate_with_resume(
    provider: TextProvider, prompt: str, model: str, budget: ContextBudget
) -> ResumedGeneration:
    """The first call, proven against `budget`, plus up to MAX_RESUMPTIONS continuations.

    `budget.num_ctx` is reused unchanged on every continuation: the model
    needs the same window to keep reading the tail it is asked to
    continue from. Continuations deliberately pass `json_output=False`:
    Ollama's `format: json` asks for one complete, self-contained body,
    which is the restart a continuation must never ask for.
    """
    options = {"num_ctx": budget.num_ctx}
    result, provenance = provider.generate(prompt, model, json_output=True, options=options)
    if prompt_was_truncated(budget, result.prompt_eval_count):
        raise PromptTruncatedError(
            f"{model}: prompt_eval_count {result.prompt_eval_count} sits at the "
            f"requested num_ctx of {budget.num_ctx}: the prompt did not fit"
        )
    text = result.text
    resumptions = 0
    while result.done_reason == LENGTH_DONE_REASON and resumptions < MAX_RESUMPTIONS:
        resumptions += 1
        tail = text[-CONTINUATION_TAIL_CHARS:]
        result, provenance = provider.generate(
            _continuation_prompt(tail), model, json_output=False, options=options
        )
        text += result.text
    if result.done_reason == LENGTH_DONE_REASON:
        raise GenerationTruncatedError(
            f"{model}: still hit the output cap after {MAX_RESUMPTIONS} resumptions"
        )
    return ResumedGeneration(text=text, provenance=provenance, resumptions=resumptions)
