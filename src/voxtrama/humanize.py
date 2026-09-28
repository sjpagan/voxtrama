"""Numbers as a person reads them, not as a program does.

Neither core nor a CLI concern by itself: the architecture says core "does not
format anything for a human reader", but engine.timeout_message needs to
say how many bytes a download was missing when it names a run's real
failure, and the CLI's progress display (cli.progress_view) needs the same
conversion for the same numbers. A module that depends on nothing and only
formats (it never calculates a fact, only represents one already computed)
is what both can import without either crossing into the other's layer.
"""

from __future__ import annotations


def human_bytes(count: float) -> str:
    """Bytes as a person reads them: 461 MB, not 483183820."""
    for unit in ("B", "KB", "MB", "GB"):
        if count < 1024 or unit == "GB":
            return f"{count:.0f} {unit}" if unit != "GB" else f"{count:.1f} {unit}"
        count /= 1024
    return f"{count:.1f} GB"


def human_duration(seconds: float) -> str:
    """A duration as someone says it out loud: 2 minutes, not 137.4 seconds."""
    if seconds < 90:
        return f"{seconds:.0f} seconds"
    minutes = seconds / 60
    if minutes < 90:
        return f"{minutes:.0f} minutes"
    return f"{minutes / 60:.1f} hours"


def human_clock(seconds: float) -> str:
    """A position within an audio track as its player would show it: 12:04, not 724 seconds."""
    total_seconds = int(seconds)
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"
