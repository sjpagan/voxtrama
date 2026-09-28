"""Windowing and label assignment: the parts that need no model to check.

These run everywhere, including CI, because they exercise arithmetic rather
than embeddings. The defect they guard against is the one that cost the most
to find: a trailing window shorter than the rest.
"""

from __future__ import annotations

import numpy as np

from voxtrama.diarization.assign import dominant_label
from voxtrama.diarization.windowing import cluster_embeddings, label_windows, make_windows


def test_a_clip_shorter_than_one_window_yields_one_window() -> None:
    assert make_windows(0.8, 1.5, 0.75) == [(0.0, 0.8)]


def test_no_window_is_shorter_than_the_nominal_length() -> None:
    """The runt-window fix: every window of a long clip is full length.

    A short trailing window produces an embedding far from every other one,
    and with a fixed speaker count it can take a whole cluster for itself.
    That is how two speakers collapsed into one during the evaluation.
    """
    for duration in (3.0, 4.3, 7.7, 18.85, 41.9):
        windows = make_windows(duration, 1.5, 0.75)
        assert all(round(end - start, 6) == 1.5 for start, end in windows), duration


def test_windows_cover_the_whole_clip() -> None:
    windows = make_windows(10.0, 1.5, 0.75)
    assert windows[0][0] == 0.0
    assert windows[-1][1] == 10.0


def test_two_distinct_groups_of_embeddings_become_two_labels() -> None:
    a = np.tile(np.array([1.0, 0.0, 0.0], dtype="float32"), (4, 1))
    b = np.tile(np.array([0.0, 1.0, 0.0], dtype="float32"), (4, 1))
    result = cluster_embeddings(np.vstack([a, b]), max_speakers=4)
    assert len(set(result.labels)) == 2
    assert result.estimated_speakers == 2


def test_the_speaker_cap_is_a_ceiling_not_a_target() -> None:
    """Two voices report two speakers even when four are allowed."""
    a = np.tile(np.array([1.0, 0.0], dtype="float32"), (5, 1))
    b = np.tile(np.array([0.0, 1.0], dtype="float32"), (5, 1))
    result = cluster_embeddings(np.vstack([a, b]), max_speakers=4)
    assert len(set(result.labels)) == 2
    assert result.estimated_speakers == 2


def test_an_estimate_beyond_the_cap_is_reported_uncapped() -> None:
    """Five voices, capped to four, still say the estimate was five."""
    groups = [np.tile(basis, (2, 1)) for basis in np.eye(5, dtype="float32")]
    result = cluster_embeddings(np.vstack(groups), max_speakers=4)
    assert len(set(result.labels)) == 4
    assert result.estimated_speakers == 5


def test_a_segment_takes_the_label_holding_most_of_its_time() -> None:
    labelled = label_windows([(0.0, 1.5), (0.75, 2.25), (1.5, 3.0)], [0, 1, 1])
    assert dominant_label(1.4, 3.0, labelled) == "spk1"


def test_a_segment_no_window_touches_has_no_label() -> None:
    """An invented label would read exactly like a real one downstream."""
    labelled = label_windows([(0.0, 1.5)], [0])
    assert dominant_label(8.0, 9.0, labelled) is None
