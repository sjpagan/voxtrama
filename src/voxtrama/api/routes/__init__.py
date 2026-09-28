"""Public surface of the API route modules."""

from voxtrama.api.routes.health import router as health_router
from voxtrama.api.routes.job_create import router as job_create_router
from voxtrama.api.routes.job_delete import router as job_delete_router
from voxtrama.api.routes.job_exports import router as job_exports_router
from voxtrama.api.routes.job_recap_export import router as job_recap_export_router
from voxtrama.api.routes.jobs_page import router as jobs_page_router
from voxtrama.api.routes.jobs_prune import router as jobs_prune_router
from voxtrama.api.routes.models import router as models_router
from voxtrama.api.routes.models_download import router as models_download_router
from voxtrama.api.routes.models_remove import router as models_remove_router
from voxtrama.api.routes.profile import router as profile_router
from voxtrama.api.routes.recording_audio import router as recording_audio_router
from voxtrama.api.routes.recording_peaks import router as recording_peaks_router
from voxtrama.api.routes.recordings import router as recordings_router
from voxtrama.api.routes.run_cancel import router as run_cancel_router
from voxtrama.api.routes.run_create import router as run_create_router
from voxtrama.api.routes.run_delete import router as run_delete_router
from voxtrama.api.routes.run_events import router as run_events_router
from voxtrama.api.routes.run_output_edit import router as run_output_edit_router
from voxtrama.api.routes.run_page import router as run_page_router
from voxtrama.api.routes.run_regenerate import router as run_regenerate_router
from voxtrama.api.routes.run_retry import router as run_retry_router
from voxtrama.api.routes.run_speaker_names import router as run_speaker_names_router
from voxtrama.api.routes.run_start import router as run_start_router
from voxtrama.api.routes.run_vitality import router as run_vitality_router
from voxtrama.api.routes.runs import router as runs_router
from voxtrama.api.routes.search import router as search_router
from voxtrama.api.routes.segment_speaker import router as segment_speaker_router
from voxtrama.api.routes.setup_download_cancel import router as setup_download_cancel_router
from voxtrama.api.routes.setup_model_remove import router as setup_model_remove_router
from voxtrama.api.routes.setup_models import router as setup_models_router
from voxtrama.api.routes.setup_privacy import router as setup_privacy_router
from voxtrama.api.routes.setup_processing import router as setup_processing_router
from voxtrama.api.routes.setup_retention import router as setup_retention_router
from voxtrama.api.routes.setup_settings import router as setup_settings_router
from voxtrama.api.routes.setup_skip import router as setup_skip_router
from voxtrama.api.routes.setup_storage import router as setup_storage_router
from voxtrama.api.routes.shell import router as shell_router
from voxtrama.api.routes.theme import router as theme_router
from voxtrama.api.routes.workflow_choices import router as workflow_choices_router
from voxtrama.api.routes.workflow_choose import router as workflow_choose_router
from voxtrama.api.routes.workflow_custom import router as workflow_custom_router
from voxtrama.api.routes.workflow_edit import router as workflow_edit_router
from voxtrama.api.routes.workflow_library import router as workflow_library_router

__all__ = [
    "health_router",
    "models_router",
    "models_download_router",
    "models_remove_router",
    "profile_router",
    "theme_router",
    "recording_audio_router",
    "recording_peaks_router",
    "recordings_router",
    "run_cancel_router",
    "run_create_router",
    "run_delete_router",
    "run_events_router",
    "run_page_router",
    "run_retry_router",
    "run_output_edit_router",
    "run_speaker_names_router",
    "run_start_router",
    "run_regenerate_router",
    "job_recap_export_router",
    "segment_speaker_router",
    "run_vitality_router",
    "runs_router",
    "setup_download_cancel_router",
    "setup_model_remove_router",
    "setup_models_router",
    "setup_processing_router",
    "setup_privacy_router",
    "setup_retention_router",
    "setup_skip_router",
    "setup_settings_router",
    "setup_storage_router",
    "job_create_router",
    "job_delete_router",
    "job_exports_router",
    "jobs_prune_router",
    "jobs_page_router",
    "search_router",
    "shell_router",
    "workflow_choices_router",
    "workflow_choose_router",
    "workflow_custom_router",
    "workflow_edit_router",
    "workflow_library_router",
]
