"""Tests for voxtrama.transcription.profiles."""

from __future__ import annotations

import pytest

from voxtrama.transcription.profiles import ModelProfile, resolve_profile


def test_low_profile_uses_small_int8():
    assert resolve_profile("low") == ModelProfile(model_size="small", compute_type="int8")


def test_base_profile_uses_medium_int8():
    assert resolve_profile("base") == ModelProfile(model_size="medium", compute_type="int8")


def test_high_profile_uses_large_v3_int8():
    # device is always "cpu" in 0.1, so "high" gets the CPU
    # compute_type from the profile table, not the GPU one.
    assert resolve_profile("high") == ModelProfile(model_size="large-v3", compute_type="int8")


def test_unknown_profile_raises():
    with pytest.raises(ValueError, match="unknown hardware profile"):
        resolve_profile("ultra")
