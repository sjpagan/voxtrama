"""The log lines OllamaProvider.generate() writes around and during one call.

Split out of ollama.py to keep that file under the project's file-length limit. A start
and an end line bracket every call. progress_logger below is the third
kind: the advancing "N of M" line that generative steps used to lack in
the terminal panel. It is possible only because `"stream": true`
(ollama_generation.build_generate_payload) delivers something in between
for it to count.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

from voxtrama.providers.base import GenerationResult

logger = logging.getLogger(__name__)

# Which part of the work a call belongs to ("Window 3/4"), set by
# engine.window_calls around each call so the three lines below name the
# window they belong to.
CALL_TAG: ContextVar[str] = ContextVar("voxtrama_call_tag", default="")


def _prefix() -> str:
    tag = CALL_TAG.get()
    return f"{tag}: " if tag else ""


# A line every this many generated characters. A measurement
# (qwen3:4b, 15s of audio) ran for 21s with nothing logged in between.
# Ollama on CPU produces tens of characters a second even for a small
# model, so a few hundred characters gives a new line every few seconds.
# That keeps the terminal panel alive without a line every second from a
# fast, GPU-backed model.
PROGRESS_CHARS_STEP = 300


def log_call_started(model: str, prompt: str, options: dict[str, Any] | None) -> None:
    """One line before the call: never the prompt itself, only its length.

    `num_ctx`, when given (engine.generation_resume's budget), is logged
    because it decides whether the model can read the whole prompt.
    """
    num_ctx = (options or {}).get("num_ctx")
    ctx_note = f", num_ctx {num_ctx}" if num_ctx is not None else ""
    logger.info(
        f"{_prefix()}sent to {model}, prompt {len(prompt)} characters "
        f"(~{len(prompt) // 4} tokens){ctx_note}",
        extra={"model": model},
    )


def log_call_done(model: str, result: GenerationResult, duration_ms: int) -> None:
    """One line after the call: duration, and the prompt-read check where Ollama reports it.

    `prompt_eval_count`, when present, is the safeguard the project asks for:
    how much of the prompt Ollama says it read, next to the limit this
    provider asked for.
    """
    extra: dict[str, Any] = {"model": model, "duration_ms": duration_ms}
    note = ""
    if result.prompt_eval_count is not None:
        note = f", read {result.prompt_eval_count} prompt tokens"
        extra["count"] = result.prompt_eval_count
    words = len(result.text.split())
    logger.info(
        f"{_prefix()}{model} done, ~{words} words in {duration_ms / 1000:.1f} s{note}", extra=extra
    )


def progress_logger(model: str) -> Callable[[int], None]:
    """A closure logging one advancing line every PROGRESS_CHARS_STEP characters.

    Mirrors the shape of engine.progress_file.activity_reporter: state that
    survives between calls, kept in a closed-over dict instead of a class
    for the one field it needs. `chars_generated` is a running total (from
    StreamAccumulator), so this fires once per threshold crossed, not once
    per NDJSON line.
    """
    state = {"last_step": 0}

    def report(chars_generated: int) -> None:
        step = chars_generated // PROGRESS_CHARS_STEP
        if step <= state["last_step"]:
            return
        state["last_step"] = step
        logger.info(
            f"{_prefix()}{model} writing, ~{chars_generated // 6} words so far",
            extra={"model": model, "count": chars_generated},
        )

    return report
