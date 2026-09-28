"""The num_ctx ceiling for one model, at setup time.

Only the model's term is computed here: `<architecture>.context_length`,
read from /api/show (providers.ollama_show). The ceiling's other term,
what memory can sustain, has no formula in this codebase: no module
converts a MachineReport's bytes into a token budget for a given model's
KV cache. Instead of inventing a discount nothing backs (a guess that
"degrades quality without saying so"), this returns the model's ceiling
unchanged. min(model_ceiling, an_unknown_second_term) is still the
model_ceiling, so leaving the second term out is correct: it is half of
the ceiling, not a wrong half. Whoever defines the memory-side term can
apply it here without moving anything else that reads
InstallationConfig.model_context_limits.
"""

from __future__ import annotations


def resolve_num_ctx_cap(context_length: int | None) -> int | None:
    """The num_ctx ceiling to store for a model, or None when it is unknown."""
    return context_length
