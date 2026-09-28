"""The guided first-run setup: measures the machine and proposes,
never decides in silence. Its one artifact is a file in the
data directory (setup.installation.InstallationConfig). Personal identity
goes on the local User row instead, not into a second model of the
same person.
"""

from __future__ import annotations

from voxtrama.setup.context_cap import resolve_num_ctx_cap
from voxtrama.setup.download_progress import (
    IN_PROGRESS_STATES,
    publish_download_state,
    read_download_job_id,
    read_download_state,
    write_download_job_id,
)
from voxtrama.setup.generative_step import (
    GenerativeProviderState,
    num_ctx_cap_for,
    probe_generative_provider,
)
from voxtrama.setup.installation import (
    InstallationConfig,
    installation_config_path,
    is_first_run,
    read_installation_config,
    write_installation_config,
)
from voxtrama.setup.profile_offers import ProfileOffer, build_profile_offers
from voxtrama.tuning.chunk_tuning import ChunkPlan, estimated_memory_gib

__all__ = [
    "ChunkPlan",
    "GenerativeProviderState",
    "IN_PROGRESS_STATES",
    "InstallationConfig",
    "ProfileOffer",
    "build_profile_offers",
    "estimated_memory_gib",
    "installation_config_path",
    "is_first_run",
    "num_ctx_cap_for",
    "probe_generative_provider",
    "publish_download_state",
    "read_download_job_id",
    "read_download_state",
    "read_installation_config",
    "resolve_num_ctx_cap",
    "write_download_job_id",
    "write_installation_config",
]
