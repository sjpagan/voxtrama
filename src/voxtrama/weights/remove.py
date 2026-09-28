"""Dropping a model's cached weights from disk (the library is managed
independently of which profile is selected).

Split from weights.fetch (the project's line cap) rather than folded into
it: fetching and removing are opposite acts on the same cache, not the
same responsibility.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from voxtrama.weights.fetch import WeightSet


def remove_weights(weights: WeightSet, models_dir: Path) -> bool:
    """Drop `weights`' cache from disk. True if there was something to drop.

    huggingface_hub's own cache layout, not this module's: a snapshot of
    `repo_id` lives under `models_dir / "models--<repo_id with / as -->"`.
    Removed with `shutil.rmtree`, tolerating an `OSError` rather than
    raising: a locked or half-written cache should leave the disk as it
    was, not crash the request that asked to clean it up. `models_dir`
    itself is never removed, and a path that resolves outside it is left
    untouched: a name built from `repo_id` is not a name to trust blindly.
    """
    cache_name = "models--" + weights.repo_id.replace("/", "--")
    target = models_dir / cache_name
    try:
        resolved_target = target.resolve()
        resolved_root = models_dir.resolve()
    except OSError:
        return False
    if resolved_root not in resolved_target.parents:
        return False
    if not resolved_target.exists():
        return False
    try:
        shutil.rmtree(resolved_target, ignore_errors=False)
    except OSError:
        return False
    return True
