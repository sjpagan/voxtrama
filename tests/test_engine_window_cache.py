"""A window the model already answered is kept for a retry."""

from __future__ import annotations

import os
import time

from voxtrama.engine.context_budget import compute_context_budget
from voxtrama.engine.generation_resume import ResumedGeneration
from voxtrama.engine.window_cache import (
    CACHE_DIRNAME,
    KEEP_SECONDS,
    forget_window,
    read_window,
    window_key,
    write_window,
)
from voxtrama.providers.base import ModelProvenance

PROVENANCE = ModelProvenance("ollama", "127.0.0.1", "m", "fp", False, False)
BUDGET = compute_context_budget("prompt", 32768)


def test_a_kept_answer_reads_back_whole(tmp_path) -> None:
    key = window_key("m", "prompt", BUDGET)
    write_window(tmp_path, key, ResumedGeneration("{}", PROVENANCE, 1))

    assert read_window(tmp_path, key) == ResumedGeneration("{}", PROVENANCE, 1)


def test_another_model_or_prompt_is_another_answer() -> None:
    key = window_key("m", "prompt", BUDGET)

    assert window_key("other", "prompt", BUDGET) != key
    assert window_key("m", "prompt 2", BUDGET) != key


def test_a_forgotten_or_unreadable_answer_is_none(tmp_path) -> None:
    key = window_key("m", "prompt", BUDGET)
    write_window(tmp_path, key, ResumedGeneration("{}", PROVENANCE, 0))
    forget_window(tmp_path, key)
    assert read_window(tmp_path, key) is None

    (tmp_path / CACHE_DIRNAME / f"{key}.json").write_text("{broken")
    assert read_window(tmp_path, key) is None
    assert read_window(None, key) is None


def test_old_answers_are_removed_when_a_new_one_is_kept(tmp_path) -> None:
    old = window_key("m", "old", BUDGET)
    write_window(tmp_path, old, ResumedGeneration("{}", PROVENANCE, 0))
    past = time.time() - KEEP_SECONDS - 60
    os.utime(tmp_path / CACHE_DIRNAME / f"{old}.json", (past, past))

    write_window(tmp_path, window_key("m", "new", BUDGET), ResumedGeneration("{}", PROVENANCE, 0))

    assert read_window(tmp_path, old) is None
