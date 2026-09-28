"""Tests for voxtrama.diarization.embedding.embed_windows: progress reporting.

Since the windows fed to the encoder are batched, progress is reported once
per batch rather than once per window. What these tests check is that the
last value reported is still the end of the last window, against the
`duration` the caller passed in. The call-count and padding behaviour that
batching introduced live in test_diarization_embedding_batching.py
(the project's file-length limit).

The encoder is faked (_load_encoder), the same way test_diarization_assign.py
fakes embed_windows itself one layer up: loading the real ECAPA model is
what test_diarization_fixture.py already covers, marked slow. torch.from_numpy
is faked too: this venv's torch was built against numpy 1.x and raises on the
real bridge (an environment mismatch, not something this test is about).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from voxtrama.diarization import embedding


class _FakeTensor:
    """Stands in for a torch.Tensor on both sides of the numpy bridge.

    Real torch.from_numpy/.numpy() raise in this venv (torch built against
    numpy 1.x, numpy 2.x installed): an environment mismatch, not something
    embed_windows' own logic is responsible for.
    """

    def __init__(self, array: np.ndarray) -> None:
        self._array = array

    def squeeze(self, dim: int) -> _FakeTensor:
        return _FakeTensor(np.squeeze(self._array, axis=dim))

    def numpy(self) -> np.ndarray:
        return self._array


class _FakeEncoder:
    def encode_batch(self, tensor: _FakeTensor, wav_lens=None) -> _FakeTensor:
        batch_size = tensor.numpy().shape[0]
        return _FakeTensor(np.zeros((batch_size, 1, 4), dtype="float32"))


def _fake_torch_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        embedding, "_load_encoder", lambda models_dir, on_download=None: _FakeEncoder()
    )
    monkeypatch.setattr(torch, "from_numpy", _FakeTensor)


def test_embed_windows_reports_the_end_of_the_last_window_of_each_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_torch_environment(monkeypatch)
    monkeypatch.setattr(embedding, "WINDOWS_PER_BATCH", 2)
    signal = np.zeros(embedding.TARGET_SAMPLE_RATE * 5, dtype="float32")
    windows = [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 5.0)]
    reported: list[tuple[float, float | None]] = []

    embedding.embed_windows(
        signal,
        windows,
        Path("unused-models"),
        duration=5.0,
        on_progress=lambda done, total: reported.append((done, total)),
    )

    # 5 windows, 2 per batch: three batches, three calls, not five, since
    # progress is reported once per batch. Every call still carries the true
    # duration, and the last one the end of the last window.
    assert reported == [(2.0, 5.0), (4.0, 5.0), (5.0, 5.0)]


def test_embed_windows_with_no_reporter_does_not_call_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A step with nothing watching ignores the callback entirely (on_progress=None)."""
    _fake_torch_environment(monkeypatch)
    signal = np.zeros(embedding.TARGET_SAMPLE_RATE, dtype="float32")

    result = embedding.embed_windows(signal, [(0.0, 1.0)], Path("unused-models"), duration=1.0)

    assert result.shape[0] == 1
