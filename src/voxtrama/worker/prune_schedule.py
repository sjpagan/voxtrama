"""The clean-up by itself: once when the worker starts, then once a day.

It applies retention too: at start-up, which is when a desktop that
was off comes back, and then daily for one that stays on.

A daemon thread beside the queue worker, not a queued job: it needs no
queue to be up, and a day-long sleep has no business holding a place in
the queue that jobs wait in. Never fatal: a clean-up that fails is logged
and tried again the next day, and the worker keeps serving jobs.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from voxtrama.config.settings import get_settings
from voxtrama.db.session import build_session_factory, session_scope
from voxtrama.housekeeping.prune import prune

logger = logging.getLogger(__name__)

EVERY_SECONDS = 24 * 3600


def _retention_days() -> int | None:
    """The installation's limit as the file says now: it may have changed."""
    get_settings.cache_clear()
    return get_settings().retention_days


def prune_once(data_dir: Path) -> None:
    """One clean-up, logged. Never raises."""
    try:
        with session_scope(build_session_factory()) as session:
            report = prune(session, data_dir, retention_days=_retention_days())
        if report.total:
            logger.info(
                "clean-up removed %d job(s), %d recording(s), %d folder(s); %d expired",
                report.jobs,
                report.recordings,
                report.folders,
                report.expired,
            )
    except Exception:
        logger.exception("clean-up failed; trying again tomorrow")


def _loop(data_dir: Path, stop: threading.Event) -> None:
    while not stop.is_set():
        prune_once(data_dir)
        stop.wait(EVERY_SECONDS)


def start_daily_prune(data_dir: Path) -> threading.Event:
    """Start the clean-up thread. Setting the returned event stops it."""
    stop = threading.Event()
    threading.Thread(target=_loop, args=(data_dir, stop), name="prune", daemon=True).start()
    return stop
