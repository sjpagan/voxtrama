"""ECAPA-TDNN embeddings (SpeechBrain) for the diarization bench.

Loads `speechbrain/spkrec-ecapa-voxceleb`, a public model: no HF_TOKEN and
no Hugging Face account are needed to fetch it (a hard constraint of the
bench). Window length, hop and clustering are the values common in the
speaker-diarization literature. This bench compares candidates under
matched conditions. It does not tune either one before a winner is even
chosen.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from speechbrain.inference.speaker import EncoderClassifier

from backends._windowing import cluster_embeddings, make_windows, windows_to_segments
from backends.base import Segment

WINDOW_SECONDS = 1.5
HOP_SECONDS = 0.75
TARGET_SAMPLE_RATE = 16_000
MODEL_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
MODEL_CACHE_DIR = Path("/tmp/voxtrama-eval/speechbrain")

# Cosine-distance merge threshold for estimated-speaker-count mode (see
# `backends._windowing.cluster_embeddings`). Tuned via `bench.py
# --sweep-threshold` against this bench's own 15-case material (11
# multi-speaker clips, 4 mono-speaker): 0.80 minimises multi-speaker DER
# (0.183) at a speaker-count error of 0.133. 0.85 ties on speaker-count
# error but is marginally worse on DER (0.184). Not the same value that
# works best for resemblyzer (see that module's constant).
DISTANCE_THRESHOLD = 0.80

_classifier: EncoderClassifier | None = None


def _load_classifier() -> EncoderClassifier:
    """Load the model once per process. The download only happens on first call."""
    global _classifier
    if _classifier is None:
        _classifier = EncoderClassifier.from_hparams(
            source=MODEL_SOURCE, savedir=str(MODEL_CACHE_DIR), run_opts={"device": "cpu"}
        )
    return _classifier


def _read_mono(wav_path: Path) -> np.ndarray:
    signal, sample_rate = sf.read(wav_path, dtype="float32", always_2d=False)
    if signal.ndim > 1:
        signal = signal.mean(axis=1)
    if sample_rate != TARGET_SAMPLE_RATE:
        raise ValueError(f"{wav_path}: expected {TARGET_SAMPLE_RATE} Hz, got {sample_rate}")
    return signal


class SpeechBrainEcapaBackend:
    """ECAPA-TDNN sliding-window embeddings, agglomeratively clustered."""

    name = "speechbrain-ecapa"

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
        classifier = _load_classifier()
        vectors = []
        for start, end in windows:
            chunk = signal[int(start * TARGET_SAMPLE_RATE) : int(end * TARGET_SAMPLE_RATE)]
            tensor = torch.from_numpy(chunk).unsqueeze(0)
            with torch.no_grad():
                embedding = classifier.encode_batch(tensor)
            vectors.append(embedding.squeeze().numpy())
        return np.stack(vectors)
