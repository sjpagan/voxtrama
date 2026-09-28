"""From a bucket's energy to the height of its bar.

The peak-based version drew a real meeting as a block: every bucket with
speech in it sat near full scale. These tests pin the two properties that
make the shape readable again: a pause drops towards zero, and a quieter
sentence is drawn lower than a louder one without vanishing.
"""

from __future__ import annotations

import numpy as np

from voxtrama.ingest.peak_scale import levels_from_energy


def _energy(amplitudes: list[float], samples: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """Per-bucket sums of squares for constant-amplitude buckets."""
    values = np.array(amplitudes, dtype=np.float64)
    counts = np.full(values.size, samples, dtype=np.int64)
    return np.square(values) * samples, counts


def test_the_loudest_bucket_is_full_height():
    sums, counts = _energy([0.5, 0.1])

    assert levels_from_energy(sums, counts)[0] == 1.0


def test_a_pause_is_drawn_near_zero():
    sums, counts = _energy([0.5, 0.0])

    assert levels_from_energy(sums, counts)[1] == 0.0


def test_quieter_speech_stays_visible_below_the_loud_part():
    # 20 dB quieter: on a linear scale this bar would be a tenth of the
    # loud one, nearly as flat as the pause. In decibels it keeps its shape.
    sums, counts = _energy([0.5, 0.05, 0.0005])

    quiet = levels_from_energy(sums, counts)[1]

    assert 0.1 < quiet < 0.9


def test_a_speech_only_recording_is_not_a_flat_block():
    """On a 22-minute call: sentences a few dB apart used to be drawn
    at almost the same height. The recording's own window spreads them."""
    loud, ordinary, soft, pause = 0.5, 0.35, 0.25, 0.0005
    sums, counts = _energy([loud] * 20 + [ordinary] * 40 + [soft] * 30 + [pause] * 10)

    levels = levels_from_energy(sums, counts)

    assert levels[0] == 1.0 and levels[-1] == 0.0
    assert levels[0] - levels[20] > 0.1 and levels[20] - levels[60] > 0.1


def test_a_silent_recording_draws_no_bars():
    sums, counts = _energy([0.0, 0.0, 0.0])

    assert levels_from_energy(sums, counts) == [0.0, 0.0, 0.0]


def test_an_empty_bucket_is_silence_not_an_error():
    sums = np.array([0.25 * 10, 0.0])
    counts = np.array([10, 0])

    assert levels_from_energy(sums, counts) == [1.0, 0.0]
