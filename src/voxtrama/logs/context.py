"""Correlation context for log lines: run_id, step and job_id.

Held in contextvars rather than passed by the caller, because the code
that needs to log a line usually does not know it is running inside a
run: it just calls logging.getLogger(__name__). `log_context` is entered
once, higher up, and every line produced underneath it picks the fields
up on its own (see logs.formatter).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_run_id: ContextVar[str | None] = ContextVar("voxtrama_run_id", default=None)
_step: ContextVar[str | None] = ContextVar("voxtrama_step", default=None)
_job_id: ContextVar[str | None] = ContextVar("voxtrama_job_id", default=None)


def current_context() -> dict[str, str]:
    """The correlation fields currently set, omitting the ones that are not."""
    fields = {"run_id": _run_id.get(), "step": _step.get(), "job_id": _job_id.get()}
    return {key: value for key, value in fields.items() if value is not None}


@contextmanager
def log_context(
    *, run_id: str | None = None, step: str | None = None, job_id: str | None = None
) -> Iterator[None]:
    """Set run_id/step/job_id for the duration of the block.

    Nests: entering a `step` inside a `run` only touches the fields it is
    given, so the outer `run_id` survives underneath it. Restores exactly
    what was there before on the way out, exception or not.
    """
    resets = []
    if run_id is not None:
        resets.append((_run_id, _run_id.set(run_id)))
    if step is not None:
        resets.append((_step, _step.set(step)))
    if job_id is not None:
        resets.append((_job_id, _job_id.set(job_id)))
    try:
        yield
    finally:
        for var, token in reversed(resets):
            var.reset(token)
