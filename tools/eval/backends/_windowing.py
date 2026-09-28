"""Shared windowing, clustering and merge logic for embedding-based backends.

Both candidate backends embed sliding windows of audio and cluster the
resulting embeddings. Keeping that machinery in one place is the only way
to guarantee they really run "the same strategy, different embedder", as
the comparison requires, rather than two implementations that quietly drift
apart over time.
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from backends.base import Segment

# Fallback cosine-distance merge threshold for the estimated-speaker-count
# mode, used only when a caller of `cluster_embeddings` does not supply its
# own `distance_threshold` (e.g. a test exercising oracle mode, which never
# reaches the branch that reads this). It is not "the" tuned value: issue
# #2's threshold sweep (`bench.py --sweep-threshold`, run against this
# bench's own 15-case material: 11 multi-speaker clips, 4 mono-speaker)
# found the optimum differs by backend (0.40 for resemblyzer, 0.80 for
# speechbrain-ecapa), so each backend module sets and passes its own value.
# See `resemblyzer.py` and `speechbrain_ecapa.py`.
DISTANCE_THRESHOLD = 0.3


def make_windows(
    duration: float, window_seconds: float, hop_seconds: float
) -> list[tuple[float, float]]:
    """Sliding (start, end) pairs covering `duration` seconds.

    The final window is clipped to `duration` rather than dropped, so a
    clip shorter than one window still yields exactly one window. But a
    clipped window that ends up much shorter than `window_seconds` is
    snapped back to full length instead (overlapping more with the
    previous one): investigating a resemblyzer DER anomaly on
    `clean-2-it.wav` found such a runt trailing window (0.85s out of a
    1.5s nominal length) producing an outlier embedding, one far enough
    from every other window that forcing a fixed speaker count let it
    hijack a whole cluster slot on its own, collapsing the two real
    speakers into a single cluster. speechbrain-ecapa tolerated the same
    runt window. resemblyzer did not, and no backend should have to.
    """
    if duration <= window_seconds:
        return [(0.0, duration)]
    windows = []
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


def cluster_embeddings(
    embeddings: np.ndarray,
    max_speakers: int,
    n_speakers: int | None = None,
    distance_threshold: float = DISTANCE_THRESHOLD,
) -> list[int]:
    """Agglomerative clustering of embeddings, speaker count estimated by default.

    With `n_speakers` given (oracle mode, for isolating counting error from
    attribution error), clustering uses exactly that many clusters and
    `distance_threshold` is unused. Otherwise the speaker count is
    *estimated* from `distance_threshold`: the bench asks the backend to
    report how many speakers it thinks are present, and forcing a fixed
    count would make `speaker_count_error` measure nothing but
    `max_speakers` itself. `max_speakers` still caps the estimate from
    above: a ceiling the bench enforces, not a target either backend is
    nudged towards.

    `distance_threshold` is a per-backend tuned value, not a shared one
    (see the module-level `DISTANCE_THRESHOLD` docstring above): callers
    are expected to pass their own, and its default here exists only for
    code that has none, such as oracle-mode calls that never reach the
    branch that reads it.
    """
    if n_speakers is not None:
        return _cluster_fixed(embeddings, min(n_speakers, len(embeddings)))
    return _cluster_estimated(embeddings, max_speakers, distance_threshold)


def _cluster_fixed(embeddings: np.ndarray, n_clusters: int) -> list[int]:
    if n_clusters <= 1:
        return [0] * len(embeddings)
    clustering = AgglomerativeClustering(n_clusters=n_clusters, metric="cosine", linkage="average")
    return list(clustering.fit_predict(embeddings))


def _cluster_estimated(
    embeddings: np.ndarray, max_speakers: int, distance_threshold: float
) -> list[int]:
    """Estimate the cluster count via `distance_threshold`, capped at `max_speakers`."""
    if len(embeddings) <= 1:
        return [0] * len(embeddings)
    estimator = AgglomerativeClustering(
        n_clusters=None, distance_threshold=distance_threshold, metric="cosine", linkage="average"
    )
    labels = estimator.fit_predict(embeddings)
    if len(set(labels)) <= max_speakers:
        return list(labels)
    return _cluster_fixed(embeddings, max_speakers)


def windows_to_segments(windows: list[tuple[float, float]], labels: list[int]) -> list[Segment]:
    """Merge contiguous windows sharing a label into single segments."""
    segments: list[Segment] = []
    for (start, end), label in zip(windows, labels, strict=True):
        speaker = f"spk{label}"
        if segments and segments[-1].speaker == speaker and segments[-1].end >= start:
            segments[-1] = Segment(segments[-1].start, end, speaker)
        else:
            segments.append(Segment(start, end, speaker))
    return segments
