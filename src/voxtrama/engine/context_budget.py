"""How large a num_ctx one generative call needs, and whether it can be trusted.

Pure arithmetic. engine.generation_resume is where a ContextBudget drives
a call, because acting on a risk or a proven truncation needs the
provider's response, which nothing here sees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# The setup measurement (InstallationConfig.
# model_context_limits) is the real ceiling. This is the floor used when
# that measurement is missing: an installation nobody has taken through
# the wizard yet, or a model chosen outside it. Well above Ollama's silent
# default of 2048 and inside every context_length measured (qwen3
# 262144, gemma3 131072), but
# still a stand-in for the real reading.
FALLBACK_MAX_CTX = 8192

# Prudent on purpose. A measured 2.8 chars/token is tuned to Italian
# prose and not ours to reuse blind.
# A smaller divisor overestimates the token count, and an overestimate
# here only costs memory, which is the safe direction to be wrong in.
CHARS_PER_TOKEN = 2.5

# A generative skill's answer has no declared size yet. Per-pass
# prompts will size one from what a pass maps over. Until then this is a
# flat, generous reservation for any one skill's JSON answer.
OUTPUT_RESERVE_TOKENS = 4096

# The fixed margin of the sizing formula in compute_context_budget.
SAFETY_MARGIN_TOKENS = 512

MIN_NUM_CTX = 4096

# The truncation check's margin: a handful of tokens for the system/template wrapping
# Ollama adds on its side of the prompt, never a fraction of an estimate.
# A field measurement has prompt_eval_count land at 2050 against
# a requested num_ctx of 2048: two tokens *over* the ceiling it was still
# counted against. This covers that kind of gap.
TRUNCATION_MARGIN_TOKENS = 32


def estimate_tokens(text: str) -> int:
    """A prudent estimate (over, never under) of how many tokens `text` costs.

    Only for sizing num_ctx generously. It is *not* a reference for how
    much of a prompt got read. A field measurement reads 7,059
    real prompt_eval_count tokens against an estimate of 10,296 on a
    25,740-character prompt that was not cut at all. An overestimate this
    wide would call that complete read a truncation if
    prompt_was_truncated compared against it. That function's docstring
    says what it compares against instead.
    """
    return math.ceil(len(text) / CHARS_PER_TOKEN)


@dataclass(frozen=True)
class ContextBudget:
    """num_ctx to ask Ollama for, and whether that number already concedes a risk."""

    num_ctx: int
    estimated_prompt_tokens: int
    at_risk: bool


def compute_context_budget(prompt: str, max_ctx: int) -> ContextBudget:
    """Estimate + output reserve + margin, clamped to `max_ctx` (at risk if it does not fit)."""
    estimated = estimate_tokens(prompt)
    needed = estimated + OUTPUT_RESERVE_TOKENS + SAFETY_MARGIN_TOKENS
    num_ctx = max(MIN_NUM_CTX, min(max_ctx, needed))
    return ContextBudget(
        num_ctx=num_ctx, estimated_prompt_tokens=estimated, at_risk=needed > max_ctx
    )


def prompt_was_truncated(budget: ContextBudget, prompt_eval_count: int | None) -> bool:
    """Point 3: prompt_eval_count landing at the num_ctx requested proves a cut.

    Never compared against estimate_tokens' output: its docstring explains
    why an estimate built to overshoot cannot be the reference for a
    truncation. The model can never read past the num_ctx it was given, so
    a prompt_eval_count at that ceiling (within TRUNCATION_MARGIN_TOKENS)
    means the prompt did not fit. Distance from a guess proves nothing.

    None (Ollama's response did not report it) is never a truncation: an
    unknown value must not invent a failure the server never signalled.
    """
    if prompt_eval_count is None:
        return False
    return prompt_eval_count >= budget.num_ctx - TRUNCATION_MARGIN_TOKENS
