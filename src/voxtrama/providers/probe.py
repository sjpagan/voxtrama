"""What `doctor` learns about a provider without running a real workflow step.

What doctor reports (reachability, latency, which models are present, and
what the provider declares about each) plus the measured
generation speed. Split from base.py (150 lines/file): these
back doctor's contract, asked once by a person, not the engine's
generate() contract asked on every step. Frozen like ModelProvenance:
never mutated after a probe or a measurement returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ProviderModel:
    """One model a provider reports it has: its name, and its size if declared.

    size_bytes lets doctor pick the smallest of several without guessing
    (measuring the largest could cost minutes, and doctor is a
    command run when something is already wrong). None when the
    provider's listing carries no size, never a 0 standing in for it.
    """

    name: str
    size_bytes: int | None


@dataclass(frozen=True)
class ProviderProbe:
    """Whether a provider answered, and what it said about itself.

    `error` carries a readable reason when `reachable` is False. Doctor
    reports this, never crashes on it, so
    TextProvider.probe() catches every ProviderError itself and returns
    this instead of raising. `latency_seconds` times the cheapest call the
    probe makes, never a generation: doctor should not have to load a
    model just to learn whether the host answers.
    """

    reachable: bool
    latency_seconds: float | None
    version: str | None
    models: tuple[ProviderModel, ...]
    error: str | None


@dataclass(frozen=True)
class GenerationSpeed:
    """One timed generation. "Real speed" is two numbers.

    A single wall-clock rate mixes generation with the minutes a large
    model can take to load (measured: 5.6s of load against 0.9s of
    generation, same call). One number either makes a fast model look
    unusable or hides what the person is waiting for. `tokens_per_second`
    and `tokens` come only from the provider's eval_count/eval_duration,
    and `load_seconds` only from its load_duration. `source` says whether
    both were declared ("provider timings") or not ("wall clock"). In the
    second case the first two stay None instead of being reconstructed
    from `wall_seconds`, which times the whole call, load included.
    """

    model: str
    tokens: int | None
    tokens_per_second: float | None
    load_seconds: float | None
    wall_seconds: float
    source: Literal["provider timings", "wall clock"]
