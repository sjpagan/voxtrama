"""What GET /models shows: the permanent library of every model
this installation manages (the three Whisper profiles, ECAPA-TDNN), and
the line at the top saying what this installation currently uses.

The Generative group reuses rendering.setup_models.ModelRowView and
setup.licences unchanged: a licence asterisk means the
same here as on step 3, with the same rendering. See
api.routes.models.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.humanize import human_bytes
from voxtrama.rendering.setup_processing import profile_display_name
from voxtrama.setup.installation import InstallationConfig
from voxtrama.weights import WeightSet


@dataclass(frozen=True)
class WeightRowView:
    """One row of the Transcription or Speakers group, exactly as
    pages/models.html shows it.
    """

    key: str
    label: str
    size_label: str
    licence: str
    page_url: str
    installed: bool
    # True when removing this row's weights means the next run has to
    # fetch them again: the active profile's row, and Speakers' row
    # whenever it is installed (ECAPA is not a profile, every run needs
    # it). An announced wait is a wait.
    redownload_notice: bool


def weight_row(
    key: str, weights: WeightSet, *, installed: bool, redownload_notice: bool
) -> WeightRowView:
    """`weights`' facts, plus what the route has already decided about it
    (a presenter formats, it does not decide). Whether the row's
    actions render while a download is in flight elsewhere (DOWNLOAD_SLOT
    is one slot for the whole installation) is the template's
    `downloading` flag, not a per-row field. It disables every row alike.
    """
    return WeightRowView(
        key=key,
        label=weights.label,
        size_label=human_bytes(weights.nominal_bytes),
        licence=weights.licence,
        page_url=weights.page_url,
        installed=installed,
        redownload_notice=redownload_notice,
    )


@dataclass(frozen=True)
class InstallationSummaryView:
    """The "what this installation uses" line at the top of the page.

    None everywhere when `configured` is False (setup never finished).
    """

    configured: bool
    profile_label: str | None
    parallelism_label: str | None
    generative_model: str | None
    context_cap_label: str | None


def installation_summary_view(config: InstallationConfig | None) -> InstallationSummaryView:
    if config is None:
        return InstallationSummaryView(
            configured=False,
            profile_label=None,
            parallelism_label=None,
            generative_model=None,
            context_cap_label=None,
        )
    cap = config.model_context_limits.get(config.ollama_model or "")
    return InstallationSummaryView(
        configured=True,
        profile_label=profile_display_name(config.hardware_profile),
        parallelism_label=f"{config.parallel_chunks} chunks × {config.cores_per_chunk} cores",
        generative_model=config.ollama_model,
        context_cap_label=f"{cap} tokens" if cap else None,
    )
