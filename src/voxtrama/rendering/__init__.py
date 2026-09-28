"""Rendering: turns rows a route has already read into what a template shows.

The architecture's fourth layer, first built here. Until now the
serialisation in api/ was the only rendering code. The architecture's rule
keeps this package thin: if a presenter needs to calculate something,
that calculation belongs in core.
"""

from __future__ import annotations

from voxtrama.rendering.assets import static_url
from voxtrama.rendering.identity import Identity, header_full_name, header_initial, read_identity
from voxtrama.rendering.model_library import (
    InstallationSummaryView,
    WeightRowView,
    installation_summary_view,
    weight_row,
)
from voxtrama.rendering.nav import BackLink, Crumb, NavItem, sidebar_items
from voxtrama.rendering.recent_activity import recent_activity_rows
from voxtrama.rendering.recordings import RecordingRow, recording_rows
from voxtrama.rendering.run_failure import FailureBanner, MemoryFacts, failure_banner_view
from voxtrama.rendering.run_page import RunPageView, RunStepRow, run_page_view
from voxtrama.rendering.run_produced import ProducedView, produced_view
from voxtrama.rendering.run_result import ResultView, result_view
from voxtrama.rendering.runs import RunRow, run_rows
from voxtrama.rendering.setup_download import DownloadView, download_view
from voxtrama.rendering.setup_models import ModelRowView, model_row_views
from voxtrama.rendering.setup_processing import (
    ChunkPlanView,
    ProfileOfferView,
    chunk_plan_view,
    machine_summary,
    profile_display_name,
    profile_offer_views,
)
from voxtrama.rendering.setup_settings import (
    ConfigFieldView,
    ProfileOption,
    SettingsOverviewView,
    profile_options,
    settings_overview_view,
)
from voxtrama.rendering.setup_steps import SetupStepRow, setup_step_rows
from voxtrama.rendering.setup_storage import DiskUsageView, disk_usage_view, profile_label
from voxtrama.rendering.theme import Theme, stored_theme, theme_choices
from voxtrama.rendering.upload_gate import BlockerView, UploadGateView, upload_gate
from voxtrama.rendering.workflow_library import WorkflowCard, WorkflowDetail, workflow_detail
from voxtrama.rendering.workflow_offers import (
    SkillOption,
    StepChoiceRow,
    WorkflowOffer,
    build_offer,
    failed_offer,
)

__all__ = [
    "upload_gate",
    "UploadGateView",
    "BlockerView",
    "recent_activity_rows",
    "BackLink",
    "ChunkPlanView",
    "ConfigFieldView",
    "Crumb",
    "DiskUsageView",
    "DownloadView",
    "FailureBanner",
    "Identity",
    "InstallationSummaryView",
    "MemoryFacts",
    "ModelRowView",
    "NavItem",
    "ProducedView",
    "ProfileOfferView",
    "ProfileOption",
    "RecordingRow",
    "ResultView",
    "RunPageView",
    "RunRow",
    "SettingsOverviewView",
    "SetupStepRow",
    "SkillOption",
    "StepChoiceRow",
    "Theme",
    "RunStepRow",
    "WeightRowView",
    "WorkflowCard",
    "WorkflowDetail",
    "WorkflowOffer",
    "build_offer",
    "chunk_plan_view",
    "disk_usage_view",
    "download_view",
    "failed_offer",
    "failure_banner_view",
    "header_full_name",
    "header_initial",
    "installation_summary_view",
    "machine_summary",
    "model_row_views",
    "profile_display_name",
    "profile_label",
    "profile_options",
    "produced_view",
    "profile_offer_views",
    "read_identity",
    "recording_rows",
    "result_view",
    "run_page_view",
    "run_rows",
    "settings_overview_view",
    "setup_step_rows",
    "sidebar_items",
    "static_url",
    "stored_theme",
    "theme_choices",
    "weight_row",
    "workflow_detail",
]
