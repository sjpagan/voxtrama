"""Loads the pinned faster-whisper model for one hardware profile.

Split out of asr.py, which grew past the project's 150-line file cap once
it gained two more parameters (cpu_threads and num_workers) to pass
down to WhisperModel.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from faster_whisper import WhisperModel

from voxtrama.weights import fetch_weights, whisper_weights

logger = logging.getLogger(__name__)


def load_model(
    model_size: str,
    model_revision: str,
    compute_type: str,
    models_dir: Path,
    cpu_threads: int,
    num_workers: int,
    on_download: Callable[[int, int | None], None] | None = None,
) -> WhisperModel:
    """Load `model_revision` of `model_size`, downloading it on first use.

    Downloading here, not at build time, is deliberate: models are
    gigabytes, and a container that fetches them before it can even
    answer a request would look broken.

    The fetch is done first and separately (voxtrama.weights) so that those
    minutes are visible: faster-whisper downloads with Hugging Face's
    progress bars disabled, which is why the first run looks frozen. By the
    time WhisperModel is constructed the files are in its cache and it
    downloads nothing.
    """
    fetch_weights(whisper_weights(model_size, model_revision), models_dir, on_download)
    # Loading takes tens of seconds and says nothing of its own. The
    # run page's activity log would otherwise sit still for all of it.
    logger.info("Loading the transcription model (Whisper %s)...", model_size)
    return WhisperModel(
        model_size,
        # Execution is CPU-only for 0.1. tuning.definition.
        # AsrTuning.device is never read here: a tuning file may
        # declare "mps" or "cuda", but honouring that
        # is a decision of its own, not a side effect of wiring up
        # cpu_threads/num_workers below.
        device="cpu",
        compute_type=compute_type,
        cpu_threads=cpu_threads,
        num_workers=num_workers,
        download_root=str(models_dir),
        revision=model_revision,
    )
