"""Sliding windows and clustering: how embeddings become speaker labels.

Ported from the measurement bench that chose this backend rather than
rewritten, so the product behaves the way the bench's numbers describe.
The bench copy stays where it is: it has to keep comparing
candidates, including ones this package will never import.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.cluster import AgglomerativeClustering

WINDOW_SECONDS = 1.5
HOP_SECONDS = 0.75

# Cosine-distance merge threshold, tuned by `tools/eval/bench.py
# --sweep-threshold` against 11 multi-speaker clips.
# It belongs to this embedder: the other candidate's optimum was 0.40, and
# sharing one value would have compared two tunings instead of two models.
DISTANCE_THRESHOLD = 0.80


def make_windows(
    duration: float, window_seconds: float = WINDOW_SECONDS, hop_seconds: float = HOP_SECONDS
) -> list[tuple[float, float]]:
    """Sliding (start, end) pairs covering `duration` seconds.

    A trailing window that would come out much shorter than `window_seconds`
    is snapped back to full length, overlapping the previous one further,
    instead of being clipped. A runt window produces an embedding far from
    every other one, and with a fixed speaker count it can take a whole
    cluster for itself. That is how two real speakers collapsed into one
    during the evaluation in #2.
    """
    if duration <= window_seconds:
        return [(0.0, duration)]
    windows: list[tuple[float, float]] = []
    start = 0.0
    while start < duration:
        end = min(start + window_seconds, duration)
        if end - start < window_seconds and windows:
            full_start = max(0.0, duration - window_seconds)
            if full_start > windows[-1][0]:
                windows.append((full_start, duration))
            break
        windows.append((start, end))
        if end >= duration:
            break
        start += hop_seconds
    return windows


@dataclass(frozen=True)
class ClusteringResult:
    """The labels clustering settled on, plus what it estimated before any cap.

    `estimated_speakers` is never itself capped: it is needed to say a fixed
    ceiling was reached, instead of a run reporting the ceiling as if it had
    been the truth all along.
    """

    labels: list[int]
    estimated_speakers: int


def cluster_embeddings(embeddings: np.ndarray, max_speakers: int) -> ClusteringResult:
    """Group embeddings by speaker, estimating how many speakers there are.

    The count is estimated from `DISTANCE_THRESHOLD` and only capped by
    `max_speakers`: a fixed count would make the system report the ceiling it
    was given rather than what it heard.
    """
    if len(embeddings) <= 1:
        return ClusteringResult(labels=[0] * len(embeddings), estimated_speakers=len(embeddings))
    estimator = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=DISTANCE_THRESHOLD,
        metric="cosine",
        linkage="average",
    )
    labels = estimator.fit_predict(embeddings)
    estimated = len(set(labels))
    if estimated <= max_speakers:
        return ClusteringResult(labels=list(labels), estimated_speakers=estimated)
    capped = AgglomerativeClustering(n_clusters=max_speakers, metric="cosine", linkage="average")
    return ClusteringResult(
        labels=list(capped.fit_predict(embeddings)), estimated_speakers=estimated
    )


def label_windows(
    windows: list[tuple[float, float]], labels: list[int]
) -> list[tuple[float, float, str]]:
    """Pair each window with the anonymous speaker label of its cluster.

    The label is `spk0`, `spk1` and so on, and never a person's name: the two are kept
    apart, and this one survives even after someone links a Person to
    it by hand.
    """
    return [
        (start, end, f"spk{label}") for (start, end), label in zip(windows, labels, strict=True)
    ]
