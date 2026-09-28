"""The windows of one generative step sent to the model at the same time.

Before this, engine.generative read the windows one after another, each
call waiting for the one before: on a real job (21 min of audio,
qwen3:4b) each window took more than two minutes, and the step took the
sum of them. This sends several at once.

Only the model call runs in a thread, with a copy of the step's
contextvars so its Activity lines land on this run and step. Everything that writes to the
database (the context budget, the provenance) stays on the step's own
thread, after the calls return, because a SQLAlchemy Session is not
shared between threads. The outputs come back in window order whatever
order the calls finish in, so window_merge joins them as before.

Each call is tagged "Window 3/4" in the log (providers.ollama_call_log),
an answered window is reported to the step's progress (`on_answered`), and
every answer is kept (engine.window_cache) so a retry sends only the rest.

How many calls run at once is Settings.parallel_windows. The model
server decides how many it really serves together: Ollama queues the
rest unless OLLAMA_NUM_PARALLEL is above 1, which is also what sets how
much memory it reserves (one num_ctx per parallel request). A limit of 1
is the old behaviour, one call at a time.
"""

from __future__ import annotations

import contextvars
import logging
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from pathlib import Path

from voxtrama.engine.context_budget import ContextBudget
from voxtrama.engine.generation_resume import ResumedGeneration, generate_with_resume
from voxtrama.engine.window_cache import read_window, window_key, write_window
from voxtrama.providers.base import TextProvider
from voxtrama.providers.ollama_call_log import CALL_TAG

logger = logging.getLogger(__name__)


class _NotSent(Exception):
    """A window skipped because an earlier one already failed the step."""


class _Calls:
    """What every window's call shares: the provider, the model, where answers are kept."""

    def __init__(self, provider, model, count, cache_dir, on_answered) -> None:
        self.provider, self.model, self.count = provider, model, count
        self.cache_dir, self.on_answered = cache_dir, on_answered
        self.failed = threading.Event()
        self.answered = 0
        self.lock = threading.Lock()

    def done(self) -> None:
        with self.lock:
            self.answered += 1
            answered = self.answered
        self.on_answered(answered, self.count)

    def call(self, prompt: str, budget: ContextBudget, number: int) -> ResumedGeneration:
        if self.failed.is_set():
            raise _NotSent
        if self.count > 1:
            CALL_TAG.set(f"Window {number}/{self.count}")
        key = window_key(self.model, prompt, budget)
        kept = read_window(self.cache_dir, key)
        if kept is not None:
            logger.info("%sanswer kept from an earlier attempt, not asked again", _tag())
            self.done()
            return kept
        try:
            generation = generate_with_resume(self.provider, prompt, self.model, budget)
        except Exception:
            self.failed.set()
            raise
        write_window(self.cache_dir, key, generation)
        self.done()
        return generation


def _tag() -> str:
    tag = CALL_TAG.get()
    return f"{tag}: " if tag else ""


def generate_windows(
    provider: TextProvider,
    prompts: Sequence[str],
    model: str,
    budgets: Sequence[ContextBudget],
    parallel: int,
    on_failure: Callable[[int], None] = lambda number: None,
    *,
    cache_dir: Path | None = None,
    on_answered: Callable[[int, int], None] = lambda done, total: None,
) -> list[ResumedGeneration]:
    """One generation per prompt, in the prompts' order, at most `parallel` at a time.

    The first window to fail, in window order, raises its own exception
    unchanged (engine.validation.error_code_for classifies it as before),
    after `on_failure` is told its index. The windows not yet sent when
    one fails are never sent: a failed step stops asking for text nobody
    will read. Those already running are waited for, so no thread is
    left talking to the model after the step has failed.
    """
    count = len(prompts)
    workers = max(1, min(parallel, count))
    calls = _Calls(provider, model, count, cache_dir, on_answered)
    if count > 1:
        logger.info("Reading the transcript in %d windows, %d at a time", count, workers)
    on_answered(0, count)
    with ThreadPoolExecutor(workers, thread_name_prefix="window") as pool:
        futures: list[Future[ResumedGeneration]] = [
            # each call carries the run and step ids its log lines are filed under
            pool.submit(contextvars.copy_context().run, calls.call, prompt, budget, number)
            for number, (prompt, budget) in enumerate(zip(prompts, budgets, strict=True), 1)
        ]
        wait(futures)
    for index, future in enumerate(futures):
        error = future.exception()
        if error is not None and not isinstance(error, _NotSent):
            on_failure(index)
            raise error
    return [future.result() for future in futures]
