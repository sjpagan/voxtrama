"""FastAPI application factory: builds the app and registers routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from voxtrama.api.errors import register_problem_handler
from voxtrama.api.routes import (
    health_router,
    job_create_router,
    job_delete_router,
    job_exports_router,
    job_recap_export_router,
    jobs_page_router,
    jobs_prune_router,
    models_download_router,
    models_remove_router,
    models_router,
    profile_router,
    recording_audio_router,
    recording_peaks_router,
    recordings_router,
    run_cancel_router,
    run_create_router,
    run_delete_router,
    run_events_router,
    run_output_edit_router,
    run_page_router,
    run_regenerate_router,
    run_retry_router,
    run_speaker_names_router,
    run_start_router,
    run_vitality_router,
    runs_router,
    search_router,
    segment_speaker_router,
    setup_download_cancel_router,
    setup_model_remove_router,
    setup_models_router,
    setup_privacy_router,
    setup_processing_router,
    setup_retention_router,
    setup_settings_router,
    setup_skip_router,
    setup_storage_router,
    shell_router,
    theme_router,
    workflow_choices_router,
    workflow_choose_router,
    workflow_custom_router,
    workflow_edit_router,
    workflow_library_router,
)
from voxtrama.api.security import SecurityMiddleware
from voxtrama.config.settings import get_settings
from voxtrama.logs import setup_logging
from voxtrama.setup.proposal import ensure_proposal

# Derived from this file's own location, same as templating.py's
# TEMPLATES_DIR: resolves correctly both from this checkout and from an
# installed wheel, where PackageLoader-style lookups on voxtrama.web would
# have to contend with it being a namespace package (no __init__.py).
STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


# Every router the app serves, in one place outside create_app: a
# module-level tuple, so _register_routes stays under the 40-line ceiling.
_ROUTERS = (
    health_router,
    models_router,
    models_download_router,
    models_remove_router,
    profile_router,
    theme_router,
    shell_router,
    search_router,
    job_create_router,
    jobs_page_router,
    job_delete_router,
    job_exports_router,
    jobs_prune_router,
    recordings_router,
    recording_audio_router,
    recording_peaks_router,
    run_create_router,
    runs_router,
    run_events_router,
    run_vitality_router,
    run_page_router,
    run_cancel_router,
    run_delete_router,
    run_retry_router,
    run_speaker_names_router,
    workflow_choices_router,
    workflow_choose_router,
    workflow_library_router,
    workflow_custom_router,
    workflow_edit_router,
    run_start_router,
    run_regenerate_router,
    job_recap_export_router,
    segment_speaker_router,
    run_output_edit_router,
    setup_processing_router,
    setup_download_cancel_router,
    setup_model_remove_router,
    setup_models_router,
    setup_privacy_router,
    setup_retention_router,
    setup_skip_router,
    setup_settings_router,
    setup_storage_router,
)


def _register_routes(app: FastAPI) -> None:
    """Every router in _ROUTERS, in one place outside create_app."""
    for router in _ROUTERS:
        app.include_router(router)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """The machine's proposal is written, and declared, before a page reads it."""
    ensure_proposal(get_settings().data_dir)
    yield


def create_app() -> FastAPI:
    """Build the Voxtrama FastAPI application.

    Logging is set up here from the raw environment, not from Settings,
    which requires VOXTRAMA_QUEUE_URL: this factory must not fail before a
    request asks for the queue. The per-run log copy is in worker/main.py.
    """
    setup_logging(get_settings().log_level)
    app = FastAPI(title="Voxtrama", lifespan=_lifespan)
    register_problem_handler(app)
    app.add_middleware(SecurityMiddleware)  # Host, Origin and headers
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    _register_routes(app)
    return app


app = create_app()
