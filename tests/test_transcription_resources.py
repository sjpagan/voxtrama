"""Tests for transcription.resources.resolve_engine_resources.

The end-to-end fallback through transcribe() has its own test in
test_transcription_asr_resources.py; these two exercise the function
directly, against the real machine and real tuning/*.yaml files this repo
ships, same standing as test_tuning_selector.py's own real-file tests.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.transcription.resources import resolve_engine_resources


def test_given_values_pass_through_when_within_what_the_machine_has(tmp_path: Path) -> None:
    cpu_threads, num_workers = resolve_engine_resources(tmp_path, 1, 1)

    assert (cpu_threads, num_workers) == (1, 1)


def test_none_falls_back_to_this_machine_s_tuning_proposal_not_a_constant(tmp_path: Path) -> None:
    cpu_threads, num_workers = resolve_engine_resources(tmp_path, None, None)

    assert cpu_threads >= 1
    assert num_workers >= 1
