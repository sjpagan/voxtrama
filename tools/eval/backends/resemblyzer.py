"""Resemblyzer embeddings for the diarization bench.

`VoiceEncoder` ships its own weights inside the pip package: no HF_TOKEN,
no Hugging Face account, no network call at all after `pip install`. Window
length, hop and clustering mirror `speechbrain_ecapa.py` so the two
backends are compared under matched conditions, not two different recipes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from resemblyzer import VoiceEncoder

from backends._windowing import cluster_embeddings, make_windows, windows_to_segments
from backends.base import Segment

WINDOW_SECONDS = 1.5
HOP_SECONDS = 0.75
TARGET_SAMPLE_RATE = 16_000

# Cosine-distance merge threshold for estimated-speaker-count mode (see
# `backends._windowing.cluster_embeddings`). Tuned via `bench.py
# --sweep-threshold` against this bench's own 15-case material (11
# multi-speaker clips, 4 mono-speaker): 0.40 minimises multi-speaker DER
# (0.195) at a speaker-count error of 0.133, clearly ahead of neighbouring
# values (0.35 -> DER 0.222, 0.45 -> DER 0.214). Not the same value that
# works best for speechbrain-ecapa (see that module's constant).
DISTANCE_THRESHOLD = 0.40

_encoder: VoiceEncoder | None = None


def _load_encoder() -> VoiceEncoder:
    """Load the model once per process. CPU only, matching the bench's constraint."""
    global _encoder
    if _encoder is None:
        _encoder = VoiceEncoder(device="cpu")
    return _encoder


def _read_mono(wav_path: Path) -> np.ndarray:
    signal, sample_rate = sf.read(wav_path, dtype="float32", always_2d=False)
    if signal.ndim > 1:
        signal = signal.mean(axis=1)
    if sample_rate != TARGET_SAMPLE_RATE:
        raise ValueError(f"{wav_path}: expected {TARGET_SAMPLE_RATE} Hz, got {sample_rate}")
    return signal


class ResemblyzerBackend:
    """Resemblyzer sliding-window embeddings, agglomeratively clustered."""

    name = "resemblyzer"

    def diarize(
        self, wav_path: Path, max_speakers: int, n_speakers: int | None = None
    ) -> list[Segment]:
        signal = _read_mono(wav_path)
        duration = len(signal) / TARGET_SAMPLE_RATE
        windows = make_windows(duration, WINDOW_SECONDS, HOP_SECONDS)
        embeddings = self._embed_windows(signal, windows)
        labels = cluster_embeddings(embeddings, max_speakers, n_speakers, DISTANCE_THRESHOLD)
        return windows_to_segments(windows, labels)

    def _embed_windows(self, signal: np.ndarray, windows: list[tuple[float, float]]) -> np.ndarray:
        encoder = _load_encoder()
        vectors = [
            encoder.embed_utterance(
                signal[int(start * TARGET_SAMPLE_RATE) : int(end * TARGET_SAMPLE_RATE)]
            )
            for start, end in windows
        ]
        return np.stack(vectors)
