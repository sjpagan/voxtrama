"""Hardware profiles: which ASR model and compute type each one runs.

This table is fixed, and a profile is never guessed from the host: a
wrong guess degrades quality without saying so, so the profile is always an explicit choice
(VOXTRAMA_HARDWARE_PROFILE, default "base"). Detecting
`minimum_model_profile` against a skill's requirement is the engine's job,
not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

HardwareProfile = Literal["low", "base", "high"]


@dataclass(frozen=True)
class ModelProfile:
    """The faster-whisper model size and compute type a profile selects."""

    model_size: str
    compute_type: str


# device is always "cpu" in 0.1 (a GPU is not a requirement), so "high"
# uses the CPU compute type from the configuration table, not the GPU one.
PROFILES: dict[HardwareProfile, ModelProfile] = {
    "low": ModelProfile(model_size="small", compute_type="int8"),
    "base": ModelProfile(model_size="medium", compute_type="int8"),
    "high": ModelProfile(model_size="large-v3", compute_type="int8"),
}


def resolve_profile(name: HardwareProfile) -> ModelProfile:
    """Look up the model and compute type for `name`.

    Raises rather than falling back to a default: a typo in
    VOXTRAMA_HARDWARE_PROFILE must fail loudly, not silently run a
    different profile than the one asked for.
    """
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError(f"unknown hardware profile: {name!r}") from None
