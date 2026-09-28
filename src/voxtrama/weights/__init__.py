"""Model weights: what a run will have to fetch, and fetching it out loud.

Weights are downloaded on first use rather than baked into the image,
which means the first run of a fresh installation spends minutes
on the network before it produces anything. The rule for that is to
announce it first. "An announced wait is a wait; an unannounced
wait is a fault."

This package exists so that both halves of that sentence have somewhere to
live: `is_cached` answers whether a run will download anything at all, before
it starts, and `fetch_weights` reports bytes while they arrive.
"""

from __future__ import annotations

from voxtrama.weights.fetch import (
    ECAPA_KEY,
    WeightSet,
    ecapa_weights,
    fetch_weights,
    is_cached,
    whisper_weights,
)
from voxtrama.weights.remove import remove_weights

__all__ = [
    "ECAPA_KEY",
    "WeightSet",
    "ecapa_weights",
    "fetch_weights",
    "is_cached",
    "remove_weights",
    "whisper_weights",
]
