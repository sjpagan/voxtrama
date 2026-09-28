"""From a bucket's energy to the height of its bar.

The first version stored the loudest sample of each bucket, normalised to
full scale. Measured on a real 21-minute meeting that produced a block:
the first half of the recording sat between 0.65 and 1.00, so every bar had
nearly the same height and the waveform told speech and pauses apart no
better than a rectangle would.

Two changes make the shape readable:

- **RMS, not peak.** A single click or plosive sets a bucket's peak. Its
  RMS is how loud the bucket is.
- **A logarithmic scale.** Loudness is heard in decibels. On a linear scale
  quiet speech and silence both sit near zero. In decibels a pause drops
  and a sentence rises.

Measured again, the decibel scale alone still drew a speech-only
recording as one flat block: every bucket that holds a sentence sits a
few dB below the loudest, so every bar came out between 0.8 and 1.0. The
window is therefore the recording's own: from its quiet end (the 5th
percentile) to its loud end (the 99.5th), never wider than
DYNAMIC_RANGE_DB, and the result is squared so the difference between a
loud and an ordinary sentence shows.

Levels are relative to the recording itself, so a quiet recording is drawn
as tall as a loud one: the player shows the shape, not the gain.
"""

from __future__ import annotations

import numpy as np

# The widest window of loudness ever drawn: a bucket more than this many
# dB below the recording's loud end is a bar of height zero.
DYNAMIC_RANGE_DB = 45.0

# Where the recording's own window starts and ends, as percentiles of its
# buckets: unaffected by a single click at the top and by digital silence
# at the bottom.
QUIET_PERCENTILE = 5.0
LOUD_PERCENTILE = 99.5

# Squaring spreads the upper part of the window, where speech lives.
CONTRAST = 2.0

_SILENCE = 1e-9


def levels_from_energy(sum_of_squares: np.ndarray, counts: np.ndarray) -> list[float]:
    """One level between 0.0 and 1.0 per bucket, on the recording's own decibel window.

    `sum_of_squares` and `counts` are per bucket, with samples already
    normalised to [-1, 1]. A bucket that received no samples is silence.
    """
    mean_square = np.divide(
        sum_of_squares, counts, out=np.zeros_like(sum_of_squares), where=counts > 0
    )
    rms = np.sqrt(mean_square)
    if float(rms.max()) <= _SILENCE:
        return [0.0] * rms.size
    decibels = 20.0 * np.log10(np.maximum(rms, _SILENCE))
    loud = float(np.percentile(decibels, LOUD_PERCENTILE))
    quiet = max(float(np.percentile(decibels, QUIET_PERCENTILE)), loud - DYNAMIC_RANGE_DB)
    if loud - quiet < 1.0:  # an even tone, or one bucket: nothing to contrast
        quiet = loud - DYNAMIC_RANGE_DB
    levels = np.clip((decibels - quiet) / (loud - quiet), 0.0, 1.0) ** CONTRAST
    return [round(float(level), 3) for level in levels]
