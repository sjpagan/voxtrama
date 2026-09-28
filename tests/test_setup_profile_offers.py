"""setup.profile_offers: the three hardware profiles, with real numbers.

MachineReports built by hand throughout, the same discipline
test_tuning_selector.py uses: this must decide correctly without the
machine it is deciding for.
"""

from __future__ import annotations

from voxtrama.diagnostics.machine import MachineReport
from voxtrama.engine.estimate import estimate_processing_seconds
from voxtrama.setup.profile_offers import build_profile_offers
from voxtrama.transcription.asr import weights_for
from voxtrama.transcription.profiles import resolve_profile


def _machine(free_disk_bytes: int | None, total_memory_bytes: int = 36 * 1024**3) -> MachineReport:
    return MachineReport(
        platform="darwin",
        architecture="arm64",
        cpu_count=16,
        performance_cores=11,
        efficiency_cores=5,
        cpu_brand="Apple M3 Pro",
        total_memory_bytes=total_memory_bytes,
        unified_memory=True,
        free_disk_bytes=free_disk_bytes,
        gpu_available=True,
        accelerator="mps",
        in_container=False,
    )


def test_every_offer_carries_the_real_model_size_and_download_bytes() -> None:
    offers = build_profile_offers(_machine(free_disk_bytes=500 * 1024**3))

    by_key = {offer.key: offer for offer in offers}
    for key in ("low", "base", "high"):
        assert by_key[key].model_size == resolve_profile(key).model_size
        assert by_key[key].download_bytes == weights_for(key).nominal_bytes


def test_every_offer_carries_the_real_processing_cost() -> None:
    offers = build_profile_offers(_machine(free_disk_bytes=500 * 1024**3))

    for offer in offers:
        expected = estimate_processing_seconds(3600, offer.key)
        assert offer.processing_seconds_per_hour == expected


def test_exactly_one_offer_is_recommended() -> None:
    offers = build_profile_offers(_machine(free_disk_bytes=500 * 1024**3))

    assert sum(offer.recommended for offer in offers) == 1


def test_a_machine_with_plenty_of_free_space_fits_every_profile() -> None:
    offers = build_profile_offers(_machine(free_disk_bytes=500 * 1024**3))

    assert all(offer.fits_free_disk for offer in offers)


def test_a_machine_short_on_space_disables_only_the_profiles_that_do_not_fit() -> None:
    high_bytes = weights_for("high").nominal_bytes
    low_bytes = weights_for("low").nominal_bytes
    # Enough for "low", not for "high": a real, known shortfall.
    just_enough_for_low = (high_bytes + low_bytes) // 2

    offers = build_profile_offers(_machine(free_disk_bytes=just_enough_for_low))
    by_key = {offer.key: offer for offer in offers}

    assert by_key["low"].fits_free_disk is True
    assert by_key["high"].fits_free_disk is False


def test_unknown_free_space_disables_nothing() -> None:
    """Unknown is never a plausible rejection, the same rule diagnostics.machine follows."""
    offers = build_profile_offers(_machine(free_disk_bytes=None))

    assert all(offer.fits_free_disk for offer in offers)
