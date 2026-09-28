"""Diarization measures: pure functions, no audio, no models.

Everything here operates on `Segment` lists so the bench can be tested
without downloading a model or reading a wav file (see `test_metrics.py`).
"""

from __future__ import annotations

import itertools

import numpy as np
from backends.base import Segment
from scipy.optimize import linear_sum_assignment


def der(reference: list[Segment], hypothesis: list[Segment]) -> float:
    """Diarization Error Rate: (missed + false alarm + confusion) / reference speech time.

    Speaker labels in `reference` and `hypothesis` are arbitrary strings
    that need not agree (a clustering backend has no reason to call its
    first speaker "spk0" and the reference "spk0" too): the optimal
    one-to-one label mapping is found with the Hungarian algorithm on
    total overlap duration, as in the standard NIST/md-eval metric.

    Overlapping speech (in either list) follows the standard per-frame
    formula: missed = max(0, n_ref - n_hyp), false_alarm = max(0, n_hyp -
    n_ref), confusion = min(n_ref, n_hyp) - n_correct, summed over the
    time grid induced by every segment boundary.
    """
    boundaries = _boundaries(reference, hypothesis)
    ref_labels = sorted({s.speaker for s in reference})
    hyp_labels = sorted({s.speaker for s in hypothesis})
    mapping = _optimal_mapping(reference, hypothesis, ref_labels, hyp_labels, boundaries)

    missed = false_alarm = confusion = ref_time = 0.0
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        duration = end - start
        active_ref = _active_speakers(reference, start, end)
        active_hyp = {mapping.get(s, s) for s in _active_speakers(hypothesis, start, end)}
        n_ref, n_hyp = len(active_ref), len(active_hyp)
        n_correct = len(active_ref & active_hyp)
        missed += max(0, n_ref - n_hyp) * duration
        false_alarm += max(0, n_hyp - n_ref) * duration
        confusion += (min(n_ref, n_hyp) - n_correct) * duration
        ref_time += n_ref * duration

    if ref_time == 0:
        return 0.0
    return (missed + false_alarm + confusion) / ref_time


def _boundaries(reference: list[Segment], hypothesis: list[Segment]) -> list[float]:
    """Every segment start/end, from either list: the grid DER is computed on."""
    points = {s.start for s in reference} | {s.end for s in reference}
    points |= {s.start for s in hypothesis} | {s.end for s in hypothesis}
    return sorted(points)


def _active_speakers(segments: list[Segment], start: float, end: float) -> set[str]:
    """Speakers whose segment fully covers [start, end), a boundary-induced interval."""
    epsilon = 1e-9
    return {s.speaker for s in segments if s.start <= start + epsilon and s.end >= end - epsilon}


def _optimal_mapping(
    reference: list[Segment],
    hypothesis: list[Segment],
    ref_labels: list[str],
    hyp_labels: list[str],
    boundaries: list[float],
) -> dict[str, str]:
    """Map each hypothesis label to the reference label it overlaps most with."""
    if not ref_labels or not hyp_labels:
        return {}
    overlap = np.zeros((len(ref_labels), len(hyp_labels)))
    ref_index = {label: i for i, label in enumerate(ref_labels)}
    hyp_index = {label: i for i, label in enumerate(hyp_labels)}
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        duration = end - start
        for ref_speaker in _active_speakers(reference, start, end):
            for hyp_speaker in _active_speakers(hypothesis, start, end):
                overlap[ref_index[ref_speaker], hyp_index[hyp_speaker]] += duration
    row_ind, col_ind = linear_sum_assignment(-overlap)
    return {hyp_labels[c]: ref_labels[r] for r, c in zip(row_ind, col_ind, strict=True)}


def speaker_count_error(reference: list[Segment], hypothesis: list[Segment]) -> int:
    """Absolute difference in distinct speaker count between the two lists."""
    ref_count = len({s.speaker for s in reference})
    hyp_count = len({s.speaker for s in hypothesis})
    return abs(ref_count - hyp_count)


def stability(runs: list[list[Segment]]) -> float:
    """Mean pairwise DER across repeated runs of the same backend on the same file.

    Zero means the backend is deterministic, or its randomness never
    changes the output. This measures run-to-run agreement, not accuracy
    against any ground truth.
    """
    if len(runs) < 2:
        return 0.0
    pairs = list(itertools.combinations(range(len(runs)), 2))
    return sum(der(runs[i], runs[j]) for i, j in pairs) / len(pairs)


def agreement(a: list[Segment], b: list[Segment]) -> float:
    """Cross-backend agreement, as a symmetrised DER.

    `der` privileges its `reference` argument (the denominator is the
    reference's speech time). Neither backend's output is a ground truth
    here, so the measure is averaged both ways round.
    """
    return (der(a, b) + der(b, a)) / 2


def cross_clip_consistency(
    clip_a: dict[str, str], clip_b: dict[str, str], shared_speakers: set[str]
) -> float:
    """Fraction of `shared_speakers` assigned the same hypothesis label in both clips.

    `clip_a` and `clip_b` map a *declared* speaker id (stable across
    clips, from fixture metadata) to the hypothesis cluster label that
    speaker was mapped to in that clip, e.g. via `_optimal_mapping`
    applied per clip by the caller.

    LIMITATION: a backend here clusters each file independently, with no
    embedding space shared across files. A label like "spk0" meaning the
    same cluster in clip_a and clip_b is a coincidence of clustering
    order, not evidence the backend recognised the same voice. This is
    therefore a weak proxy, valid only for clips whose metadata declares
    the same speaker present in both. It is not a real cross-clip identity
    check and must not be read as one.
    """
    if not shared_speakers:
        return 0.0
    matches = sum(1 for speaker in shared_speakers if clip_a.get(speaker) == clip_b.get(speaker))
    return matches / len(shared_speakers)
