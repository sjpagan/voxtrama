"""What the "Local processing" step shows: turns a MachineReport, a
TuningFile's ChunkPlan and setup.profile_offers' ProfileOffers into the
strings and flags pages/setup_local_processing.html renders. The
rendering layer sits between the route and the template so neither has
to format a byte count or a warning sentence itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.diagnostics.machine import MachineReport
from voxtrama.humanize import human_bytes
from voxtrama.setup.profile_offers import ProfileOffer
from voxtrama.transcription.asr import weights_for
from voxtrama.tuning.chunk_tuning import ChunkPlan, estimated_memory_gib

GIB = 1024**3

_ACCELERATOR_LABELS = {"mps": "Metal", "cuda": "CUDA"}
_DISPLAY_NAMES = {"low": "Efficient", "base": "Balanced", "high": "Maximum accuracy"}
_SUBTITLES = {
    "low": "Best for everyday use",
    "base": "Great quality and speed",
    "high": "Highest quality transcripts",
}
# Every profile offers the same kind of model (the line under each
# model's name): a whisper size, never a
# second task. So this is one constant, not a third dict keyed by offer.
_KIND_LABEL = "Automatic speech recognition"


def profile_display_name(key: str) -> str:
    """ "Efficient" / "Balanced" / "Maximum accuracy" for a low/base/high key.

    Shared with the step 4 summary ("Ready to start") so the profile
    reads the same word there as on its own card.
    """
    return _DISPLAY_NAMES[key]


def machine_summary(machine: MachineReport) -> str:
    """ "Apple M3 Pro · 11 performance cores · 5 efficiency · 36 GB unified · Metal"."""
    accelerator = _ACCELERATOR_LABELS.get(machine.accelerator or "", "no accelerator")
    parts = [machine.cpu_brand or "Unknown CPU", _core_phrase(machine), _memory_phrase(machine)]
    parts.append(accelerator)
    return " · ".join(parts)


def _core_phrase(machine: MachineReport) -> str:
    if machine.performance_cores is not None and machine.efficiency_cores is not None:
        performance, efficiency = machine.performance_cores, machine.efficiency_cores
        return f"{performance} performance cores · {efficiency} efficiency"
    if machine.cpu_count is not None:
        return f"{machine.cpu_count} cores"
    return "unknown cores"


def _memory_phrase(machine: MachineReport) -> str:
    if machine.total_memory_bytes is None:
        return "unknown memory"
    gib = machine.total_memory_bytes / GIB
    return f"{gib:.0f} GB {'unified' if machine.unified_memory else 'RAM'}"


@dataclass(frozen=True)
class ProfileOfferView:
    """One profile card, exactly as pages/setup_local_processing.html shows it."""

    key: str
    display_name: str
    subtitle: str
    model_label: str
    kind_label: str
    download_label: str
    per_hour_label: str
    recommended: bool
    available: bool
    unavailable_reason: str | None
    cached: bool
    licence: str
    page_url: str


def profile_offer_views(
    offers: list[ProfileOffer], free_disk_bytes: int | None, cached_keys: set[str]
) -> list[ProfileOfferView]:
    return [_offer_view(offer, free_disk_bytes, offer.key in cached_keys) for offer in offers]


def _offer_view(offer: ProfileOffer, free_disk_bytes: int | None, cached: bool) -> ProfileOfferView:
    minutes = offer.processing_seconds_per_hour / 60
    reason = None
    if not offer.fits_free_disk and free_disk_bytes is not None:
        needed, free = human_bytes(offer.download_bytes), human_bytes(free_disk_bytes)
        reason = f"Needs {needed}, only {free} free"
    weights = weights_for(offer.key)
    return ProfileOfferView(
        key=offer.key,
        display_name=_DISPLAY_NAMES[offer.key],
        subtitle=_SUBTITLES[offer.key],
        model_label=f"whisper-{offer.model_size}",
        kind_label=_KIND_LABEL,
        download_label=human_bytes(offer.download_bytes),
        per_hour_label=f"≈ {minutes:.0f} min",
        recommended=offer.recommended,
        available=offer.fits_free_disk,
        unavailable_reason=reason,
        cached=cached,
        licence=weights.licence,
        page_url=weights.page_url,
    )


@dataclass(frozen=True)
class ChunkPlanView:
    """The Fine-tune panel's two fields plus the arithmetic shown under them."""

    cores_per_chunk: int
    parallel_chunks: int
    total_cores_label: str
    memory_label: str
    exceeds_recommended: bool
    warning: str | None
    # The cap the form must carry. Without it the browser accepts a number
    # the server then quietly clamps, and a person sees a value change
    # under their hands with nothing saying why.
    available_cores: int | None


def chunk_plan_view(plan: ChunkPlan, model_download_bytes: int) -> ChunkPlanView:
    gib = estimated_memory_gib(plan, model_download_bytes)
    warning = None
    if plan.exceeds_recommended:
        recommended = plan.recommended_parallel_chunks
        warning = f"Above the {recommended} chunks recommended for this machine"
    return ChunkPlanView(
        cores_per_chunk=plan.cores_per_chunk,
        parallel_chunks=plan.parallel_chunks,
        total_cores_label=f"≈ {plan.total_cores} cores",
        memory_label=f"needs ~{gib:.1f} GB",
        exceeds_recommended=plan.exceeds_recommended,
        warning=warning,
        available_cores=plan.available_cores,
    )
