"""Tests for voxtrama.transcription.vad."""

from __future__ import annotations

from voxtrama.transcription.vad import vad_parameters


def test_vad_parameters_match_adr_0009():
    # The VAD configuration fixes these four values; a change here
    # made without deciding it is what this test blocks.
    assert vad_parameters() == {
        "threshold": 0.5,
        "min_speech_duration_ms": 250,
        "min_silence_duration_ms": 700,
        "speech_pad_ms": 200,
    }
