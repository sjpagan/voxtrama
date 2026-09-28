"""Tests for voxtrama.diarization.assign: the speaker-cap declaration.

Real embeddings need the ECAPA model and real audio, which
test_diarization_fixture.py already covers (marked slow). These tests
replace read_mono_16k, make_windows and embed_windows with fakes, so
assign_speakers' own bookkeeping (what it writes on the Transcript, what
it logs) is exercised on every run, not just when a model is cached.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest

from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.diarization import assign
from voxtrama.diarization.assign import assign_speakers

LOGGER_NAME = "voxtrama.diarization.assign"


def _distinct_speaker_embeddings(count: int) -> np.ndarray:
    """Two windows per speaker, `count` speakers clearly apart (orthogonal)."""
    return np.vstack([np.tile(basis, (2, 1)) for basis in np.eye(count, dtype="float32")])


def _fake_windows(count: int) -> list[tuple[float, float]]:
    return [(float(i), float(i + 1)) for i in range(count)]


def _transcript() -> Transcript:
    transcript = Transcript(
        recording_id="r1",
        language="en",
        model_name="medium",
        model_revision="test",
        hardware_profile="base",
    )
    transcript.segments = [Segment(start=0.0, end=10.0, text="", confidence=1.0)]
    return transcript


def _diarise(
    monkeypatch: pytest.MonkeyPatch, embeddings: np.ndarray, max_speakers: int
) -> Transcript:
    windows = _fake_windows(len(embeddings))
    monkeypatch.setattr(assign, "read_mono_16k", lambda path: np.zeros(1, dtype="float32"))
    monkeypatch.setattr(assign, "make_windows", lambda duration: windows)
    monkeypatch.setattr(
        assign,
        "embed_windows",
        lambda signal, win, models_dir, duration, on_download=None, on_progress=None: embeddings,
    )
    return assign_speakers(
        _transcript(), Path("unused.wav"), Path("unused-models"), max_speakers=max_speakers
    )


def test_five_voices_beyond_the_cap_are_reported_not_hidden(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A run with five voices says five, not a silently rounded four."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        transcript = _diarise(monkeypatch, _distinct_speaker_embeddings(5), max_speakers=4)

    assert transcript.speaker_estimate == 5
    assert transcript.speaker_cap == 4
    assert any("5" in r.message and "4" in r.message for r in caplog.records)


def test_an_estimate_within_the_cap_is_not_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        transcript = _diarise(monkeypatch, _distinct_speaker_embeddings(2), max_speakers=4)

    assert transcript.speaker_estimate == 2
    assert transcript.speaker_cap == 4
    assert caplog.records == []
