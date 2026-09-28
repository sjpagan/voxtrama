"""The home page's first-run card: the proposal in force, said out loud.

Shown only while there is no voxtrama.toml. It names the profile and the
two chunking numbers Voxtrama is using because the machine proposed them
(setup.proposal), links to the guided setup to change them, and, when the
transcription model is not on disk yet, offers its download in one click
on the home page itself: the one thing a first job cannot do without.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.readiness import Readiness, ReadinessReport
from voxtrama.humanize import human_bytes
from voxtrama.rendering.setup_download import DownloadView, download_view
from voxtrama.setup.download_progress import IN_PROGRESS_STATES, read_download_state
from voxtrama.setup.proposal import proposal_in_force
from voxtrama.transcription.asr import weights_for
from voxtrama.transcription.profiles import resolve_profile


@dataclass(frozen=True)
class FirstRunCard:
    hardware_profile: str
    model_size: str
    cores_per_chunk: int
    parallel_chunks: int
    download_size: str
    model_missing: bool
    downloading: bool
    download: DownloadView | None


def first_run_card(settings: Settings, readiness: ReadinessReport) -> FirstRunCard | None:
    """The card, or None once voxtrama.toml exists (the proposal is no longer in force)."""
    proposal = proposal_in_force(settings.data_dir)
    if proposal is None:
        return None
    profile = proposal.hardware_profile
    state = read_download_state(settings.data_dir)
    downloading = state is not None and state.state in IN_PROGRESS_STATES
    return FirstRunCard(
        hardware_profile=profile,
        model_size=resolve_profile(profile).model_size,  # type: ignore[arg-type]
        cores_per_chunk=proposal.cores_per_chunk,
        parallel_chunks=proposal.parallel_chunks,
        download_size=human_bytes(weights_for(profile).nominal_bytes),  # type: ignore[arg-type]
        model_missing=readiness.models_ready.state is not Readiness.READY,
        downloading=downloading,
        download=download_view(state) if state is not None and state.state != "succeeded" else None,
    )
