"""Tests for the batching fix: the switch, not the mechanism.

Before the fix, embed_windows called encode_batch once per window. On 21
minutes of audio, about 1700 calls of one window each, measured at 0.51x
real time. Batches of 32 measured at 4.04x. The suite of 1113 tests that
existed before this one never noticed the difference, because nothing
asserted the call count: that is the gap this file closes.

The encoder is faked the same way test_diarization_embedding.py fakes it.
See that file's docstring for why torch.from_numpy is faked too.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import torch

from voxtrama.diarization import embedding


class _FakeTensor:
    def __init__(self, array: np.ndarray) -> None:
        self._array = array

    def squeeze(self, dim: int) -> _FakeTensor:
        return _FakeTensor(np.squeeze(self._array, axis=dim))

    def numpy(self) -> np.ndarray:
        return self._array


class _CountingEncoder:
    """Counts how many times encode_batch is called, and nothing else."""

    def __init__(self) -> None:
        self.calls = 0

    def encode_batch(self, tensor: _FakeTensor, wav_lens=None) -> _FakeTensor:
        self.calls += 1
        batch_size = tensor.numpy().shape[0]
        return _FakeTensor(np.zeros((batch_size, 1, 4), dtype="float32"))


class _EchoEncoder:
    """Returns, per row, the mean of only that row's real (unpadded) samples.

    A batch pads every chunk to the group's longest one. If the padding or
    the wav_lens fraction that marks where the real audio ends were wrong,
    this would mix a window's own samples with padding, or with another
    window's samples, and the mean would no longer identify the window it
    came from.
    """

    def encode_batch(self, tensor: _FakeTensor, wav_lens: torch.Tensor) -> _FakeTensor:
        padded = tensor.numpy()
        max_len = padded.shape[1]
        means = [
            padded[row, : round(frac * max_len)].mean()
            for row, frac in enumerate(wav_lens.tolist())
        ]
        return _FakeTensor(np.array(means, dtype="float32").reshape(-1, 1, 1))


def test_embed_windows_calls_encode_batch_once_per_batch_not_once_per_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encoder = _CountingEncoder()
    monkeypatch.setattr(embedding, "_load_encoder", lambda models_dir, on_download=None: encoder)
    monkeypatch.setattr(torch, "from_numpy", _FakeTensor)

    window_count = 70
    windows = [(float(i), float(i + 1)) for i in range(window_count)]
    signal = np.zeros(embedding.TARGET_SAMPLE_RATE * (window_count + 1), dtype="float32")

    embedding.embed_windows(signal, windows, Path("unused-models"), duration=float(window_count))

    assert encoder.calls == math.ceil(window_count / embedding.WINDOWS_PER_BATCH)


def test_embed_windows_pads_a_batch_without_mixing_up_which_window_is_which(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        embedding, "_load_encoder", lambda models_dir, on_download=None: _EchoEncoder()
    )
    monkeypatch.setattr(torch, "from_numpy", _FakeTensor)

    # Three windows sharing one batch, each a different length (8000, 24000
    # and 4000 samples) and filled with its own constant, so the mean of its
    # real samples identifies it independently of order or padding.
    signal = np.concatenate(
        [
            np.full(8000, 0.1, dtype="float32"),
            np.full(24000, 0.5, dtype="float32"),
            np.full(4000, 0.9, dtype="float32"),
        ]
    )
    windows = [(0.0, 0.5), (0.5, 2.0), (2.0, 2.25)]

    vectors = embedding.embed_windows(signal, windows, Path("unused-models"), duration=2.25)

    assert vectors[:, 0] == pytest.approx([0.1, 0.5, 0.9])
