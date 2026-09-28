"""weights.fetch.remove_weights: dropping a cached snapshot from disk.

No network in any of these: the huggingface_hub cache layout is built by
hand (`models--<repo_id with / as -->`), never fetched.
"""

from __future__ import annotations

from pathlib import Path

from voxtrama.weights.fetch import WeightSet
from voxtrama.weights.remove import remove_weights


def _weights(repo_id: str) -> WeightSet:
    return WeightSet(
        label="test model",
        repo_id=repo_id,
        revision=None,
        patterns=["*"],
        nominal_bytes=0,
        licence="MIT",
        page_url=f"https://huggingface.co/{repo_id}",
    )


def test_removes_the_cache_folder_huggingface_hub_would_have_made(tmp_path: Path) -> None:
    weights = _weights("openai/whisper-small")
    cache_dir = tmp_path / "models--openai--whisper-small"
    cache_dir.mkdir()
    (cache_dir / "snapshot.bin").write_text("weights")

    removed = remove_weights(weights, tmp_path)

    assert removed is True
    assert not cache_dir.exists()
    # models_dir itself is never the thing removed.
    assert tmp_path.exists()


def test_nothing_to_remove_returns_false(tmp_path: Path) -> None:
    weights = _weights("openai/whisper-small")

    assert remove_weights(weights, tmp_path) is False


def test_a_cache_path_resolving_outside_models_dir_is_left_untouched(tmp_path: Path) -> None:
    """A repo_id is not a name to trust blindly: a symlink planted where
    the cache folder would sit, pointing outside models_dir, must not be
    followed and cleaned out.
    """
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    outside = tmp_path / "not-a-model-cache"
    outside.mkdir()
    (outside / "important.txt").write_text("not this model's to delete")
    weights = _weights("escape/repo")
    (models_dir / "models--escape--repo").symlink_to(outside, target_is_directory=True)

    removed = remove_weights(weights, models_dir)

    assert removed is False
    assert outside.exists()
    assert (outside / "important.txt").exists()
