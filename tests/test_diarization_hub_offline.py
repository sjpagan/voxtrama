"""ECAPA must not ask Hugging Face for files it already has.

The home page promises "Runs entirely on your machine". Measured before this
guard: four requests to huggingface.co per run, during `diarize`, for weights
`fetch_weights` had just put on disk. No audio leaves, but the fact that this
machine is running that model does, on every run.
"""

from __future__ import annotations

from pathlib import Path

import huggingface_hub.constants as hub

from voxtrama.diarization.encoder import _hub_offline


def test_the_cache_points_at_our_models_dir_inside_the_guard() -> None:
    """The fault that mattered: from_hparams looked in huggingface_hub's own
    default cache (/root/.cache/huggingface/hub in the container) while
    weights.fetch had put ECAPA under models_dir, the only mounted directory.
    speechbrain therefore fetched its own copy on every run, into a place a
    rebuild wipes.
    """
    with _hub_offline(Path("/data/models")):
        assert hub.HF_HUB_CACHE == "/data/models"


def test_the_hub_is_offline_inside_the_guard() -> None:
    """The flag is forced on the constant, not through the environment:
    huggingface_hub reads HF_HUB_OFFLINE once at import, so setting the
    variable at runtime has no effect (measured).
    """
    with _hub_offline(Path("/data/models")):
        assert hub.HF_HUB_OFFLINE is True


def test_the_previous_setting_comes_back() -> None:
    """Narrow on purpose: an installation that legitimately works online is
    unaffected everywhere else, and weights.fetch keeps being able to
    download: that is the one moment a person explicitly asked for it.
    """
    before, cache_before = hub.HF_HUB_OFFLINE, hub.HF_HUB_CACHE

    with _hub_offline(Path("/data/models")):
        pass

    assert hub.HF_HUB_OFFLINE is before
    assert hub.HF_HUB_CACHE == cache_before


def test_the_setting_comes_back_even_when_loading_fails() -> None:
    """A model that fails to load must not leave the whole process offline."""
    before, cache_before = hub.HF_HUB_OFFLINE, hub.HF_HUB_CACHE

    try:
        with _hub_offline(Path("/data/models")):
            raise RuntimeError("loading blew up")
    except RuntimeError:
        pass

    assert hub.HF_HUB_OFFLINE is before
    assert hub.HF_HUB_CACHE == cache_before
