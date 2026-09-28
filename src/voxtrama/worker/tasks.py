"""Job bodies executed by the RQ worker: each translates a job into one core call."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.migrations_state import MigrationsStateError, is_up_to_date
from voxtrama.db.models.run import Run
from voxtrama.db.session import build_session_factory, session_scope
from voxtrama.engine.failure import fail_run
from voxtrama.engine.run import execute_run
from voxtrama.logs import log_context
from voxtrama.setup.download_progress import publish_download_state
from voxtrama.setup.first_run import settle_after_first_run
from voxtrama.transcription.asr import weights_for
from voxtrama.weights import ECAPA_KEY, WeightSet, ecapa_weights, fetch_weights

logger = logging.getLogger(__name__)


def _weight_set_for(weight_key: str) -> WeightSet:
    """The WeightSet behind one library key: one of the three
    hardware profiles, or ECAPA_KEY. ECAPA is never treated as a fourth
    profile, since a profile is a choice and ECAPA is not one.
    """
    if weight_key == ECAPA_KEY:
        return ecapa_weights()
    return weights_for(weight_key)  # type: ignore[arg-type]


def execute_run_job(run_id: str) -> None:
    """Open a database session and execute the Run with the given id.

    Everything logged underneath (by this call or anything it calls)
    carries run_id from here on, without either having to pass
    it explicitly.
    """
    # A work horse RQ forks inherits the cache worker.main.main()
    # already populated at process start, before the guided setup wrote
    # voxtrama.toml, for a worker started ahead of the first-run wizard.
    # Clearing it once per job, rather than once per process, is the right
    # level: settings stay stable for the whole job, but each new job
    # picks up the file as it stands right now.
    get_settings.cache_clear()
    with log_context(run_id=run_id), session_scope(build_session_factory()) as session:
        if _refuse_if_schema_behind(session, run_id):
            return
        execute_run(session, run_id)
        settle_after_first_run(session, run_id, get_settings().data_dir)


def _refuse_if_schema_behind(session: Session, run_id: str) -> bool:
    """Fail the run outright instead of executing it against a stale schema.

    Measured on real audio: a run that starts anyway can transcribe for
    minutes before dying on a table a later migration would have created.
    By then the queue had already accepted work the database could not
    finish. api.routes.run_create refuses the same gap before a Run even
    exists. This is the same check for a Run that was already queued when
    the schema fell behind, or a worker started before `docker compose up
    migrate` ran. Returns True when it failed the run, so the caller skips
    execute_run rather than running it anyway.
    """
    try:
        up_to_date = is_up_to_date(session.get_bind())
        detail = "database is not at Alembic's head revision"
    except MigrationsStateError as exc:
        up_to_date = False
        detail = str(exc)
    if up_to_date:
        return False
    run = session.get(Run, run_id)
    if run is not None:
        fail_run(session, run, RuntimeError(detail), code="migrations_pending")
    return True


def _download_reporter(data_dir: Path, weights: WeightSet) -> Callable[[int, int | None], None]:
    """Publishes each download tick under the progress file a Run's own uses.

    A module-level factory rather than a closure inside download_model_job:
    that body sits against the 40-line function ceiling, and needed one
    line of its own for the cache it has to drop.
    """

    def on_progress(done: int, total: int | None) -> None:
        publish_download_state(
            data_dir,
            "running",
            model_label=weights.label,
            done_bytes=done,
            total_bytes=total or weights.nominal_bytes,
        )

    return on_progress


def download_model_job(weight_key: str) -> None:
    """Download one library key's own weights in the background.

    The blocking POST this replaces sat inside gunicorn's own 120-second
    worker timeout (Dockerfile). whisper-medium alone needs more than
    that at the floor bandwidth engine.timeout already assumes. Here the
    HTTP request that enqueues this job returns immediately. Only this
    background job waits, reporting itself through the same progress-file
    mechanism a Run's own download already uses (weights.fetch's
    on_progress callback, engine.progress_file underneath it).
    """
    get_settings.cache_clear()  # Forked cache may predate the installation file
    settings = get_settings()
    weights = _weight_set_for(weight_key)
    publish_download_state(
        settings.data_dir, "running", model_label=weights.label, total_bytes=weights.nominal_bytes
    )
    on_progress = _download_reporter(settings.data_dir, weights)

    try:
        fetch_weights(weights, settings.models_dir, on_progress)
    except Exception as exc:
        logger.exception("model download failed")
        publish_download_state(
            settings.data_dir, "failed", model_label=weights.label, message=str(exc)
        )
        raise
    publish_download_state(
        settings.data_dir,
        "succeeded",
        model_label=weights.label,
        done_bytes=weights.nominal_bytes,
        total_bytes=weights.nominal_bytes,
    )
