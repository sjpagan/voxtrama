"""Tests for the diarization measures: no audio, no models.

Every case is built by hand: DER's own correctness cannot be checked
against a real backend's output, since a real backend's DER is exactly
what this bench exists to measure.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from backends._windowing import cluster_embeddings
from backends.base import Backend, Segment
from bench import run_bench
from metrics import agreement, cross_clip_consistency, der, speaker_count_error, stability
from rttm import read_rttm, write_rttm


def test_der_is_zero_on_permuted_labels() -> None:
    reference = [Segment(0, 5, "alice"), Segment(5, 10, "bob")]
    hypothesis = [Segment(0, 5, "spk1"), Segment(5, 10, "spk0")]
    assert der(reference, hypothesis) == 0.0


def test_der_is_one_on_empty_hypothesis() -> None:
    reference = [Segment(0, 5, "alice"), Segment(5, 10, "bob")]
    assert der(reference, []) == 1.0


def test_der_counts_missed_speech() -> None:
    reference = [Segment(0, 10, "alice")]
    hypothesis = [Segment(0, 4, "spk0")]
    # 6 of 10 reference seconds have no hypothesis speech: pure miss.
    assert der(reference, hypothesis) == 0.6


def test_der_counts_false_alarm() -> None:
    reference = [Segment(0, 10, "alice")]
    hypothesis = [Segment(0, 10, "spk0"), Segment(10, 14, "spk0")]
    # The tail [10, 14) has hypothesis speech but no reference speaker at
    # all: 4 seconds of pure false alarm over the reference's 10 seconds.
    assert der(reference, hypothesis) == 0.4


def test_der_counts_extra_hypothesis_speaker_as_false_alarm() -> None:
    reference = [Segment(0, 10, "alice")]
    hypothesis = [Segment(0, 10, "spk0"), Segment(0, 10, "spk1")]
    # spk0 maps to alice (full overlap) and is correct. spk1 is a second,
    # unmapped, active speaker throughout: since two hypothesis speakers
    # are active against one reference speaker, the standard formula
    # counts the extra one as false alarm, for the full 10 seconds.
    assert der(reference, hypothesis) == 1.0


def test_speaker_count_error_on_known_cases() -> None:
    reference = [Segment(0, 5, "alice"), Segment(5, 10, "bob")]
    matching = [Segment(0, 5, "spk0"), Segment(5, 10, "spk1")]
    one_missing = [Segment(0, 10, "spk0")]
    assert speaker_count_error(reference, matching) == 0
    assert speaker_count_error(reference, one_missing) == 1


def test_stability_is_zero_on_identical_runs() -> None:
    run = [Segment(0, 5, "spk0"), Segment(5, 10, "spk1")]
    assert stability([run, list(run), list(run)]) == 0.0


def test_stability_is_positive_when_runs_disagree() -> None:
    run_a = [Segment(0, 10, "spk0")]
    run_b = [Segment(0, 5, "spk0"), Segment(5, 10, "spk1")]
    assert stability([run_a, run_b]) > 0.0


def test_agreement_is_symmetric() -> None:
    a = [Segment(0, 10, "spk0")]
    b = [Segment(0, 5, "spk0"), Segment(5, 10, "spk1")]
    assert agreement(a, b) == agreement(b, a)


def test_cross_clip_consistency_matches_and_mismatches() -> None:
    clip_a = {"alice": "spk0", "bob": "spk1"}
    clip_b = {"alice": "spk0", "bob": "spk0"}
    assert cross_clip_consistency(clip_a, clip_b, {"alice"}) == 1.0
    assert cross_clip_consistency(clip_a, clip_b, {"alice", "bob"}) == 0.5


def test_cross_clip_consistency_is_zero_with_no_shared_speakers() -> None:
    assert cross_clip_consistency({}, {}, set()) == 0.0


def test_cluster_embeddings_oracle_mode_respects_n_speakers() -> None:
    # Four near-identical embeddings would collapse to a single estimated
    # cluster. Oracle mode must still return exactly n_speakers clusters.
    embeddings = np.array([[1.0, 0.0]] * 4)
    labels = cluster_embeddings(embeddings, max_speakers=4, n_speakers=3)
    assert len(set(labels)) == 3


def test_rttm_round_trip(tmp_path: Path) -> None:
    segments = [Segment(0.0, 4.5, "alice"), Segment(4.5, 9.25, "bob")]
    path = tmp_path / "clip.rttm"
    write_rttm(path, "clip", segments)
    assert read_rttm(path) == segments


class FakeBackend:
    """A `Backend` that returns fixed segments, to exercise `bench.py` without models."""

    name = "fake"

    def diarize(
        self, wav_path: Path, max_speakers: int, n_speakers: int | None = None
    ) -> list[Segment]:
        return [Segment(0.0, 1.0, "spk0"), Segment(1.0, 2.0, "spk1")]


class UnderCountingBackend:
    """A `Backend` that always reports one speaker unless given the true count.

    Exercises the fix this file is testing: `speaker_count_error` must be
    non-zero in "estimated" mode (the backend guesses wrong) and zero in
    "oracle" mode (given the true count, it produces exactly that many).
    """

    name = "undercounting"

    def diarize(
        self, wav_path: Path, max_speakers: int, n_speakers: int | None = None
    ) -> list[Segment]:
        count = n_speakers if n_speakers is not None else 1
        edges = [i * (2.0 / count) for i in range(count + 1)]
        return [Segment(edges[i], edges[i + 1], f"spk{i}") for i in range(count)]


def _write_silent_wav(path: Path, seconds: float) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(b"\x00\x00" * int(seconds * 16_000))


def test_bench_runs_fake_backend_end_to_end(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_silent_wav(input_dir / "clip.wav", seconds=2.0)
    write_rttm(
        input_dir / "clip.rttm",
        "clip",
        [Segment(0.0, 1.0, "alice"), Segment(1.0, 2.0, "bob")],
    )

    backend: Backend = FakeBackend()
    out_dir = tmp_path / "results"
    results = run_bench(input_dir, [backend], runs=3, max_speakers=4, out_dir=out_dir)

    # A reference RTTM triggers both modes: 3 runs each, estimated and oracle.
    assert len(results) == 6
    assert {r.mode for r in results} == {"estimated", "oracle"}
    assert all(r.der == 0.0 for r in results)
    assert all(r.speaker_count_error == 0 for r in results)
    assert sorted(out_dir.glob("*.json")) != []


def test_speaker_count_error_reacts_to_a_wrong_estimate(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_silent_wav(input_dir / "clip.wav", seconds=2.0)
    write_rttm(
        input_dir / "clip.rttm",
        "clip",
        [Segment(0.0, 1.0, "alice"), Segment(1.0, 2.0, "bob")],
    )

    backend: Backend = UnderCountingBackend()
    results = run_bench(input_dir, [backend], runs=1, max_speakers=4, out_dir=tmp_path / "results")

    estimated = [r for r in results if r.mode == "estimated"]
    oracle = [r for r in results if r.mode == "oracle"]
    assert all(r.speaker_count_error == 1 for r in estimated)
    assert all(r.speaker_count_error == 0 for r in oracle)
