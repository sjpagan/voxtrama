"""The three hardware profiles offered at setup, with their real numbers.

The low/base/high table is fixed. This only reads what each would
cost on this machine (model size, download bytes, minutes per hour of
audio), reusing transcription.asr.weights_for (the same lookup
diagnostics.readiness_models already trusts) and engine.estimate (the
honest-cost module), never a second table of its own.
diagnostics.advice.advise_profile is the recommendation already
built for `doctor`: reused unchanged, so the wizard's "recommended" card
and `doctor`'s suggestion can never disagree.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.diagnostics.advice import advise_profile
from voxtrama.diagnostics.machine import MachineReport
from voxtrama.engine.estimate import estimate_processing_seconds
from voxtrama.transcription.asr import weights_for
from voxtrama.transcription.profiles import HardwareProfile, resolve_profile

SECONDS_PER_HOUR = 3600
PROFILE_KEYS: tuple[HardwareProfile, ...] = ("low", "base", "high")


@dataclass(frozen=True)
class ProfileOffer:
    """One hardware profile's real cost on this machine, nothing invented."""

    key: HardwareProfile
    model_size: str
    download_bytes: int
    processing_seconds_per_hour: float
    recommended: bool
    fits_free_disk: bool


def build_profile_offers(machine: MachineReport) -> list[ProfileOffer]:
    """The three fixed profiles, each with its measured cost.

    `fits_free_disk` is True whenever free space could not be read
    (diagnostics.machine's rule: unknown is never a plausible zero, and
    never a plausible rejection either). Only a *known* shortfall disables
    a card.
    """
    suggested, _ = advise_profile(machine)
    return [_offer(key, machine, suggested) for key in PROFILE_KEYS]


def recommended_key(offers: list[ProfileOffer]) -> str:
    """The `recommended` offer's key, or "base" if somehow none is."""
    return next((offer.key for offer in offers if offer.recommended), "base")


def _offer(key: HardwareProfile, machine: MachineReport, suggested: str | None) -> ProfileOffer:
    weights = weights_for(key)
    free = machine.free_disk_bytes
    fits = free is None or free >= weights.nominal_bytes
    return ProfileOffer(
        key=key,
        model_size=resolve_profile(key).model_size,
        download_bytes=weights.nominal_bytes,
        processing_seconds_per_hour=estimate_processing_seconds(SECONDS_PER_HOUR, key),
        recommended=key == (suggested or "base"),
        fits_free_disk=fits,
    )
