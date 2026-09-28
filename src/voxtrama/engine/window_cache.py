"""A window the model already answered is not asked again.

A job interrupted during the recap (the worker restarted, the machine went
to sleep, a stop and a retry) used to start the step over: on a real
job each of four windows took about ten minutes with qwen3:4b. Every
answer is now kept in the data folder under the hash of what produced it
(model, options, prompt). A retry, a regenerated job or a job restarted
after an interruption finds the windows already answered and sends only
the others. A different prompt, model or context budget is a different
hash, so nothing stale is ever reused.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

from voxtrama.engine.context_budget import ContextBudget
from voxtrama.engine.generation_resume import ResumedGeneration
from voxtrama.providers.base import ModelProvenance

logger = logging.getLogger(__name__)

CACHE_DIRNAME = "window-cache"
# Answers older than this are removed when a new one is written: a retry
# comes within hours, and the folder must not grow with every job forever.
KEEP_SECONDS = 14 * 24 * 3600


def window_key(model: str, prompt: str, budget: ContextBudget) -> str:
    """The hash naming one window's answer: what was asked, of which model, with what room."""
    digest = hashlib.sha256()
    for part in (model, str(budget.num_ctx), prompt):
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _path(cache_dir: Path, key: str) -> Path:
    return cache_dir / CACHE_DIRNAME / f"{key}.json"


def read_window(cache_dir: Path | None, key: str) -> ResumedGeneration | None:
    """The kept answer, or None when there is none or it cannot be read."""
    if cache_dir is None:
        return None
    try:
        data = json.loads(_path(cache_dir, key).read_text(encoding="utf-8"))
        return ResumedGeneration(
            text=data["text"],
            provenance=ModelProvenance(**data["provenance"]),
            resumptions=int(data["resumptions"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_window(cache_dir: Path | None, key: str, generation: ResumedGeneration) -> None:
    """Keep the answer; a folder that cannot be written only costs a future retry."""
    if cache_dir is None:
        return
    target = _path(cache_dir, key)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".part")
        partial.write_text(json.dumps(asdict(generation)), encoding="utf-8")
        partial.replace(target)
        _prune(target.parent, time.time() - KEEP_SECONDS)
    except OSError:
        logger.warning("could not keep a window's answer for a later retry")


def forget_window(cache_dir: Path | None, key: str) -> None:
    """Drop a kept answer that turned out unusable, so a retry asks again."""
    if cache_dir is not None:
        _path(cache_dir, key).unlink(missing_ok=True)


def _prune(folder: Path, older_than: float) -> None:
    for kept in folder.glob("*.json"):
        if kept.stat().st_mtime < older_than:
            kept.unlink(missing_ok=True)
