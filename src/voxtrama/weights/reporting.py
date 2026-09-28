"""A tqdm that reports bytes instead of drawing a bar.

Hugging Face draws download progress with tqdm and lets a caller substitute
the class it uses. Substituting it is how a download can report itself without
anyone having to parse terminal output: no bar is ever drawn, and the numbers
go wherever the caller sends them.

Three things about how `snapshot_download` uses this class decide the shape of
what follows, and all three were found by watching a real download rather than
by reading the signature:

- it builds **more than one** byte counter (one for bytes off the network,
  one for bytes reconstructed onto disk), and they count the same download
  twice. Adding them together doubles the figure;
- it also builds a counter for *files* ("Fetching 4 files"). Adding that 4 to
  a total of bytes produced "10 MB of 4 B (258259375%)";
- the byte counters start at `total=0` and are told their real total later,
  which is why their description starts as "Reconstructing (incomplete
  total...)". Reading `total` in the constructor reads that zero, and the
  caller ends up with a figure and no denominator. So it is read at each
  update instead.

One more, from tqdm rather than from Hugging Face: a disabled bar returns
from `update()` without touching its own counter, and huggingface_hub
disables bars freely. Reading `self.n` looked tidier and reported zero for
every download whose bar was off, so the bytes are counted here.
"""

from __future__ import annotations

from collections.abc import Callable

# (bytes so far, total bytes when known)
ProgressCallback = Callable[[int, int | None], None]


def reporting_tqdm(on_progress: ProgressCallback, fallback_total: int | None = None):
    """Build a tqdm subclass that reports one download's byte count.

    `fallback_total` stands in while the real total is unknown: the nominal
    size the announcement already quoted. "175 MB of 484 MB" is a wait
    someone can plan around. "175 MB" is not.
    """
    from huggingface_hub.utils import tqdm as hf_tqdm

    # The first byte counter to move is the one followed. The others
    # are ignored rather than summed, because they are the same bytes counted
    # a second time.
    followed: list[object] = []
    seen = 0

    class ReportingTqdm(hf_tqdm):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # tqdm's own convention: unit="B" counts bytes, anything else
            # counts something that is not bytes.
            self.counts_bytes = kwargs.get("unit") == "B"

        def update(self, n=1):
            nonlocal seen
            result = super().update(n)
            if not self.counts_bytes:
                return result
            if not followed:
                followed.append(self)
            if followed[0] is not self:
                return result
            seen += n or 0
            total = self.total if self.total else fallback_total
            on_progress(seen, int(total) if total else None)
            return result

    return ReportingTqdm
