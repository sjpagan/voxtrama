"""What the "Private storage" step's usage bar shows.

Turns the (total, used, free) bytes api.routes.setup_storage reads with
`shutil.disk_usage` into the labels and the bar's fraction, so the
template computes none of them. `None` in, `None` out: a
volume this process could not read is unknown, not zero free space.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.humanize import human_bytes
from voxtrama.rendering.setup_processing import profile_display_name
from voxtrama.transcription.profiles import resolve_profile


@dataclass(frozen=True)
class DiskUsageView:
    """The free-space line and bar pages/setup_private_storage.html renders."""

    free_label: str
    used_of_total_label: str
    free_fraction: float


def disk_usage_view(usage: tuple[int, int, int] | None) -> DiskUsageView | None:
    if usage is None:
        return None
    total, used, free = usage
    fraction = free / total if total else 0.0
    return DiskUsageView(
        free_label=f"{human_bytes(free)} free",
        used_of_total_label=f"{human_bytes(used)} used of {human_bytes(total)}",
        free_fraction=fraction,
    )


def profile_label(profile: str) -> str:
    """ "low" -> "Efficient · whisper-small", ready for the "Ready to start" summary."""
    model_size = resolve_profile(profile).model_size
    return f"{profile_display_name(profile)} · whisper-{model_size}"
