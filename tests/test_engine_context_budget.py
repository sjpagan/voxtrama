"""engine.context_budget: pure arithmetic, no I/O anywhere.

prompt_was_truncated's own cases use a field measurement verbatim
(25,740-character prompt, ~10,296 estimated tokens at CHARS_PER_TOKEN):
prompt_eval_count 2,050 against a requested num_ctx of 2,048 (truncated:
Ollama's own default, no options passed), and 7,059 against 16,384
(not truncated). They never use the estimate, which lands far from either of
these without saying anything about a cut.
"""

from __future__ import annotations

import pytest

from voxtrama.engine.context_budget import (
    MIN_NUM_CTX,
    OUTPUT_RESERVE_TOKENS,
    SAFETY_MARGIN_TOKENS,
    ContextBudget,
    compute_context_budget,
    estimate_tokens,
    prompt_was_truncated,
)


def test_estimate_tokens_rounds_up_never_down():
    assert estimate_tokens("x" * 10) == 4  # exactly 4.0 tokens at CHARS_PER_TOKEN
    assert estimate_tokens("x" * 11) == 5  # one char over: rounds up, not down


def test_a_small_prompt_never_asks_for_less_than_the_floor():
    """OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS already clears MIN_NUM_CTX on their
    own, so the floor is a documented safety net here, not something this
    particular prompt can trigger. The assertion is the invariant, not the number.
    """
    budget = compute_context_budget("short", max_ctx=100_000)

    assert budget.num_ctx >= MIN_NUM_CTX
    assert budget.at_risk is False


def test_a_prompt_needing_more_than_the_ceiling_is_clamped_and_flagged():
    """The call still gets a num_ctx, but the risk is not hidden."""
    budget = compute_context_budget("x" * 100_000, max_ctx=4096)

    assert budget.num_ctx == 4096
    assert budget.at_risk is True


def test_num_ctx_covers_estimate_plus_output_and_margin_when_it_fits():
    prompt = "x" * 1000
    budget = compute_context_budget(prompt, max_ctx=1_000_000)

    expected = estimate_tokens(prompt) + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
    assert budget.num_ctx == expected
    assert budget.at_risk is False


@pytest.mark.parametrize(
    ("num_ctx", "prompt_eval_count", "expected"),
    [
        (2048, None, False),  # unknown is never manufactured into a truncation
        (2048, 2050, True),  # the field measurement: the default, uncut
        (16384, 7059, False),  # the same prompt, this time not cut
    ],
)
def test_prompt_was_truncated_reads_prompt_eval_count_against_num_ctx_not_the_estimate(
    num_ctx: int, prompt_eval_count: int | None, expected: bool
) -> None:
    # estimated_prompt_tokens is irrelevant here on purpose: see
    # prompt_was_truncated's own docstring for why it is never compared
    # against it, only against the num_ctx requested.
    budget = ContextBudget(num_ctx=num_ctx, estimated_prompt_tokens=10_296, at_risk=False)

    assert prompt_was_truncated(budget, prompt_eval_count) is expected
