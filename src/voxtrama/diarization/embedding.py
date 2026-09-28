"""Turning audio windows into ECAPA-TDNN speaker embeddings, in batches.

The encoder (loading, caching, keeping speechbrain offline once cached)
lives in `encoder.py`, split out by the project's file-length limit.
This module reads audio and calls that encoder. It does not decide what
model or where it lives.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from voxtrama.diarization.encoder import _load_encoder

TARGET_SAMPLE_RATE = 16_000

# Windows fed to encode_batch together, rather than one at a time.
# Measured in the worker container, ECAPA on CPU, 48 windows of 1.5s:
# batch=1 ran at 0.51x real time (the unbatched behaviour, ~1700 calls for
# 21 minutes of audio). batch=32 with torch's default thread count ran at
# 4.04x. Batching amortises per-call overhead, not per-sample work, so
# raising torch's thread count alone (batch=1, threads=20: still 0.51x)
# does nothing. Only grouping the calls helps.
WINDOWS_PER_BATCH = 32


def read_mono_16k(wav_path: Path) -> np.ndarray:
    """Read `wav_path` as a mono float32 signal, refusing any other rate.

    Resampling belongs to whoever prepares the audio, not here: silently
    accepting a rate the model was not trained on would degrade attribution
    without anything in the result saying so.
    """
    import soundfile as sf

    signal, sample_rate = sf.read(wav_path, dtype="float32", always_2d=False)
    if signal.ndim > 1:
        signal = signal.mean(axis=1)
    if sample_rate != TARGET_SAMPLE_RATE:
        raise ValueError(f"{wav_path}: expected {TARGET_SAMPLE_RATE} Hz, got {sample_rate}")
    return signal


def _encode_batch(encoder, chunks: list[np.ndarray]) -> list[np.ndarray]:
    """Pad `chunks` to the batch's longest and encode them together.

    Windows are not always exactly the same length: `make_windows` returns a
    single short window whenever `duration <= window_seconds`, and elsewhere
    `int(end * TARGET_SAMPLE_RATE) - int(start * TARGET_SAMPLE_RATE)` can be
    one sample short of the nominal length through float rounding. So a batch
    is padded to its own longest chunk rather than stacked as-is. `wav_lens`
    (a fraction of the longest chunk per row, as
    `EncoderClassifier.encode_batch` requires) tells speechbrain which part
    of each padded row is real audio and which is padding.
    """
    import torch

    max_len = max(len(chunk) for chunk in chunks)
    padded = np.zeros((len(chunks), max_len), dtype="float32")
    for row, chunk in enumerate(chunks):
        padded[row, : len(chunk)] = chunk
    wav_lens = torch.tensor([len(chunk) / max_len for chunk in chunks])
    tensor = torch.from_numpy(padded)
    with torch.no_grad():
        embeddings = encoder.encode_batch(tensor, wav_lens=wav_lens)
    # [batch, 1, dim]: squeeze(1) rather than squeeze() so a batch of one
    # keeps its batch dimension instead of collapsing to a single vector.
    return list(embeddings.squeeze(1).numpy())


def embed_windows(
    signal: np.ndarray,
    windows: list[tuple[float, float]],
    models_dir: Path,
    duration: float,
    on_download: Callable[[int, int | None], None] | None = None,
    on_progress: Callable[[float, float | None], None] | None = None,
) -> np.ndarray:
    """One embedding vector per window, stacked in the order given.

    `duration` is assign_speakers' own figure, not recomputed here from the
    windows: the last window may end short of the audio's actual length,
    and the total this reports has to be the same one a viewer already
    knows the recording's length as.

    Windows are grouped into batches of `WINDOWS_PER_BATCH` before being
    encoded, so `on_progress` is called once per batch rather than
    once per window. It gets the `end` of the batch's last window, the same
    value it would have reported for that window before batching.
    """
    encoder = _load_encoder(models_dir, on_download)
    vectors = []
    for batch_start in range(0, len(windows), WINDOWS_PER_BATCH):
        batch = windows[batch_start : batch_start + WINDOWS_PER_BATCH]
        chunks = [
            signal[int(start * TARGET_SAMPLE_RATE) : int(end * TARGET_SAMPLE_RATE)]
            for start, end in batch
        ]
        vectors.extend(_encode_batch(encoder, chunks))
        if on_progress is not None:
            on_progress(batch[-1][1], duration)
    return np.stack(vectors)
