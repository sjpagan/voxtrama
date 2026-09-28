"""Turning readings into a suggested profile, and into warnings worth reading.

`doctor` advises, it never applies. The reason: a
profile guessed wrong degrades quality in silence, and the slowness then
gets blamed on the product instead of on a setting nobody was told
about. So this returns a recommendation and the sentence that justifies
it, and something else writes it into .env.

The opposite guard matters too: "a diagnostic that always says
everything is fine stops being read". Hence `warnings`, which is allowed
to come back empty but is not allowed to be decorative.
"""

from __future__ import annotations

from voxtrama.diagnostics.machine import MachineReport

GIB = 1024**3

# The hardware profile table, read as thresholds: "≤ 8 GB, dated CPU" -> low,
# "16 GB, modern CPU" -> base, "≥ 32 GB, or a GPU" -> high.
LOW_MAX_MEMORY_BYTES = 8 * GIB
HIGH_MIN_MEMORY_BYTES = 32 * GIB

# Enough for the "base" weights (about 1.5 GB), the diarisation model and
# room for the recordings and run outputs that follow them.
COMFORTABLE_FREE_DISK_BYTES = 10 * GIB


def advise_profile(machine: MachineReport) -> tuple[str | None, str]:
    """Suggest a hardware profile and say why, or decline to suggest one.

    Declining matters: without a memory reading any suggestion would be a
    coin toss presented as advice, and it is better that the user
    chose than have us guess for them.
    """
    memory = machine.total_memory_bytes
    if memory is None:
        return None, "memory could not be read on this platform, so no profile is suggested"
    gib = memory / GIB
    if memory <= LOW_MAX_MEMORY_BYTES:
        return (
            "low",
            f"{gib:.0f} GiB of memory: the 'small' model fits comfortably, larger ones do not",
        )
    if memory >= HIGH_MIN_MEMORY_BYTES:
        return "high", f"{gib:.0f} GiB of memory: enough for 'large-v3', the most accurate model"
    return "base", f"{gib:.0f} GiB of memory: the 'medium' model is the best fit"


def warnings(machine: MachineReport) -> list[str]:
    """Everything worth saying out loud about this machine, possibly nothing."""
    found: list[str] = []
    free = machine.free_disk_bytes
    if free is not None and free < COMFORTABLE_FREE_DISK_BYTES:
        found.append(
            f"only {free / GIB:.1f} GiB free where the data directory lives: "
            "model weights alone need about 1.5 GB, and recordings accumulate"
        )
    if machine.cpu_count is not None and machine.cpu_count < 4:
        found.append(
            f"{machine.cpu_count} CPU core(s): transcription is CPU-bound and will be slow"
        )
    if machine.gpu_available:
        found.append("a GPU is visible, but 0.1 runs every profile on CPU: it will not be used")
    return found
