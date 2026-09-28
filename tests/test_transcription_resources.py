"""Tests for transcription.resources.resolve_engine_resources.

The end-to-end fallback through transcribe() has its own test in
test_transcription_asr_resources.py; these two exercise the function
directly, against the real machine and real tuning/*.yaml files this repo
ships, same standing as test_tuning_selector.py's own real-file tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.machine import use_machine_with_cores

from voxtrama.transcription.resources import resolve_engine_resources


def test_given_values_pass_through_when_within_what_the_machine_has(tmp_path: Path) -> None:
    cpu_threads, num_workers = resolve_engine_resources(tmp_path, 1, 1)

    assert (cpu_threads, num_workers) == (1, 1)


def test_none_falls_back_to_this_machine_s_tuning_proposal_not_a_constant(tmp_path: Path) -> None:
    cpu_threads, num_workers = resolve_engine_resources(tmp_path, None, None)

    assert cpu_threads >= 1
    assert num_workers >= 1


def test_cpu_threads_is_the_full_product_num_workers_stays_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No chunking exists yet, so the whole budget lands on cpu_threads and
    num_workers stays 1: a second faster-whisper worker never runs unless
    transcribe() is itself called from more than one thread.
    """
    use_machine_with_cores(monkeypatch, 20)

    cpu_threads, num_workers = resolve_engine_resources(tmp_path, 4, 2)

    assert (cpu_threads, num_workers) == (8, 1)


def test_the_product_is_capped_at_the_cores_the_machine_has(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """cores_per_chunk and parallel_chunks are each capped on their own by
    plan_for against the same ceiling, so their product can still overrun
    it (8 * 8 = 64 on a 10-core machine): the product needs its own cap.
    """
    use_machine_with_cores(monkeypatch, 10)

    cpu_threads, num_workers = resolve_engine_resources(tmp_path, 8, 8)

    assert (cpu_threads, num_workers) == (10, 1)


def test_no_available_cores_reading_leaves_the_product_uncapped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """available_cores returning None (unknown hardware) must not invent a
    ceiling: the product passes through as asked, same as plan_for's own
    factors already do in that case.

    The machine is still given plenty of cores so plan_for's own cap on
    each factor does not itself reduce cores_per_chunk/parallel_chunks
    before the product is even taken; only the product's own cap, patched
    here to see an unknown reading, is under test.
    """
    use_machine_with_cores(monkeypatch, 20)
    monkeypatch.setattr("voxtrama.transcription.resources.available_cores", lambda machine: None)

    cpu_threads, num_workers = resolve_engine_resources(tmp_path, 4, 2)

    assert (cpu_threads, num_workers) == (8, 1)
