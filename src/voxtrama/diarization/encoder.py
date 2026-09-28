"""Loading the ECAPA-TDNN encoder, and keeping it offline once it is cached.

Split out of embedding.py (the project's file-length limit), once batching
pushed that file past it. This module owns the model's lifecycle (download,
cache, offline guard). embedding.py turns audio into vectors.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from voxtrama.weights import ecapa_weights, fetch_weights, is_cached

MODEL_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"

logger = logging.getLogger(__name__)

_encoder = None


def _load_encoder(models_dir: Path, on_download: Callable[[int, int | None], None] | None = None):
    """Load the encoder once per process, downloading it on first call.

    speechbrain and torch are imported here rather than at module level so
    that importing this package (the architecture tests and the CLI both
    do) does not pull a multi-hundred-megabyte stack into memory for
    code paths that never diarise anything.

    The weights are fetched first and separately (voxtrama.weights), for the
    same reason as the ASR model: speechbrain downloads them without saying
    so, and a first run that sits silent for minutes reads as a fault.
    """
    global _encoder
    if _encoder is None:
        weights = ecapa_weights()
        # fetch_weights resolves the revision on the Hub even when every
        # file is already here, so asking is_cached first is the difference
        # between one request per run and none. is_cached is the same check the
        # pre-run download announcement makes (weights/__init__), not a second
        # opinion about what "already downloaded" means.
        if not is_cached(weights, models_dir):
            fetch_weights(weights, models_dir, on_download)
        from speechbrain.inference.speaker import EncoderClassifier

        logger.info("Loading the speaker model (ECAPA-TDNN)...")  # Seconds of silence otherwise

        snapshot = _pinned_snapshot(weights, models_dir)
        with _hub_offline(models_dir):
            _encoder = EncoderClassifier.from_hparams(
                source=snapshot,
                # hyperparams.yaml names the checkpoints by repository, which
                # would resolve "main" again: point it at the same folder.
                overrides={"pretrained_path": snapshot},
                savedir=str(models_dir / "speechbrain-ecapa"),
                run_opts={"device": "cpu"},
            )
    return _encoder


def _pinned_snapshot(weights, models_dir: Path) -> str:
    """The folder of the pinned revision, already fetched: speechbrain reads it as is.

    For security: given the repository's name, speechbrain would
    resolve "main" in the cache, not the revision weights.fetch pinned.
    """
    from huggingface_hub import snapshot_download

    return snapshot_download(
        weights.repo_id,
        revision=weights.revision,
        cache_dir=str(models_dir),
        allow_patterns=weights.patterns,
        local_files_only=True,
    )


@contextmanager
def _hub_offline(models_dir: Path) -> Iterator[None]:
    """Point speechbrain at the weights we already fetched, and keep it there.

    Two faults, one cause. `from_hparams` looked for ECAPA in
    huggingface_hub's *default* cache (`/root/.cache/huggingface/hub` inside
    the container, measured), while weights.fetch had put the files under
    `models_dir`, the one directory the compose file mounts. So speechbrain
    ignored them and fetched its own copy, every run, into a directory that
    does not survive a rebuild: hence four requests to huggingface.co per run,
    and `models/speechbrain-ecapa` sitting at 0 bytes.

    Setting the cache alone would already stop the downloads. Offline is
    forced as well so that a revalidation cannot creep back in: the home page
    promises "Runs entirely on your machine", and after fetch_weights there is
    nothing left to ask the Hub about.

    Both are forced on the constants rather than through the environment.
    huggingface_hub reads `HF_HUB_OFFLINE` once at import, so setting the
    variable at runtime does nothing (measured). And setting it in
    compose.yaml would reach weights.fetch's own `snapshot_download` too,
    which *must* be able to download: that is the one moment a person
    explicitly asked for it, from the guided setup.

    Kept narrow: it covers this call and restores what was there before,
    even if loading raises, so an installation that legitimately works online
    is unaffected everywhere else.
    """
    import huggingface_hub.constants as hub

    was_offline, was_cache = hub.HF_HUB_OFFLINE, hub.HF_HUB_CACHE
    hub.HF_HUB_OFFLINE, hub.HF_HUB_CACHE = True, str(models_dir)
    try:
        yield
    finally:
        hub.HF_HUB_OFFLINE, hub.HF_HUB_CACHE = was_offline, was_cache
