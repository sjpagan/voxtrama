"""Worker process entrypoint: consumes jobs from the configured queue."""

from __future__ import annotations

import logging

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.session import build_session_factory, session_scope
from voxtrama.engine.auto_resume import resume_interrupted
from voxtrama.engine.reconcile import reconcile_orphan_runs
from voxtrama.engine.reconcile_step_backfill import close_orphaned_steps
from voxtrama.logs import setup_logging
from voxtrama.queue.rq_backend import RQBackend, serve_worker
from voxtrama.setup.proposal import ensure_proposal
from voxtrama.worker.prune_schedule import start_daily_prune

logger = logging.getLogger(__name__)


def main() -> None:
    """Start the RQ worker using the configured queue URL."""
    ensure_proposal(get_settings().data_dir)  # Declared, before any job reads it
    settings = get_settings()
    setup_logging(settings.log_level, runs_dir=get_paths(settings.data_dir).runs_dir)
    _reconcile_orphans_before_serving(settings.queue_url)
    # After reconciling, so a run just closed as interrupted is judged by
    # the clean-up with its real state.
    start_daily_prune(settings.data_dir)
    serve_worker(settings.queue_url)


def _reconcile_orphans_before_serving(queue_url: str) -> None:
    """Close any Run a previous worker left `running` when it died.

    Also closes any RunStep a Run left `running` when it closed before that
    was fixed (see close_orphaned_steps's docstring). That is a one-time
    backfill: from now on close_run itself never leaves one behind. Never
    fatal: a worker that cannot reconcile must still start and serve new
    jobs, rather than stay down because a past run could not be closed.
    """
    try:
        with session_scope(build_session_factory()) as session:
            queue = RQBackend(queue_url)
            runs: list = []
            closed = reconcile_orphan_runs(session, queue, into=runs)
            closed_steps = close_orphaned_steps(session)
            resumed = resume_interrupted(session, queue, runs)
        if closed:
            logger.info("reconciled %d orphaned run(s)", closed)
        if closed_steps:
            logger.info("reconciled %d orphaned step(s)", closed_steps)
        if resumed:
            logger.info("resumed %d interrupted run(s) from where they stopped", resumed)
    except Exception:
        logger.exception("orphan-run reconciliation failed; starting the worker anyway")


if __name__ == "__main__":
    main()
