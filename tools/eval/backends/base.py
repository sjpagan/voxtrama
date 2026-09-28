"""The contract every diarization backend must satisfy.

Kept free of any dependency on `voxtrama`: this bench compares
candidate backends before any of them is wired into the product, and it
must keep working even if the package underneath it is refactored or
does not exist yet in this checkout.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Protocol


class Segment(NamedTuple):
    """One speaker turn, in seconds, half-open on `end`."""

    start: float
    end: float
    speaker: str


class Backend(Protocol):
    """A diarization backend the bench can run and measure."""

    name: str

    def diarize(
        self, wav_path: Path, max_speakers: int, n_speakers: int | None = None
    ) -> list[Segment]:
        """Return the speaker turns found in `wav_path`.

        The speaker count is estimated, capped at `max_speakers`, unless
        `n_speakers` is given: an oracle mode used to separate counting
        error from attribution error when a reference is available.
        """
        ...
