"""Builds the run-level sections of a manifest: run, input, environment, languages, workflow.

Split from builder.py, which assembles the whole Manifest from these plus
the per-step section it builds itself. Kept apart so neither file grows
past the project's size limit.
"""

from __future__ import annotations

from datetime import datetime

from voxtrama import __version__
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, is_final
from voxtrama.db.models.transcript import Transcript
from voxtrama.manifest.environment import ManifestEnvironment
from voxtrama.manifest.schema import (
    LanguageProvenance,
    ManifestDestination,
    ManifestInput,
    ManifestLanguage,
    ManifestLanguages,
    ManifestRun,
    ManifestWorkflow,
)
from voxtrama.manifest.workflow_copy import workflow_definition_sha256
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Workflow

# The two ingest paths there are. Not stored as a third column on
# Recording: whether source_url is set already says which one a row took,
# and a stored flag could drift from that.
_PROVENANCE_LOCAL_FILE = "local_file"
_PROVENANCE_URL = "url"


def iso_ms(value: datetime | None) -> str | None:
    """UTC timestamp at fixed millisecond precision.

    isoformat() alone varies its digit count with the microsecond value,
    and two manifests that should compare identical would diff on that
    alone.
    """
    return None if value is None else value.isoformat(timespec="milliseconds")


def run_info(run: Run) -> ManifestRun:
    # User-chosen roots are not implemented yet: every run
    # writes under the configured data directory, the only root there is.
    destination = ManifestDestination(root="data_dir", path=f"runs/{run.id}")
    return ManifestRun(
        id=run.id,
        state=str(run.state),
        final=is_final(run.state),
        created_at=iso_ms(run.created_at) or "",
        started_at=iso_ms(run.started_at),
        finished_at=iso_ms(run.finished_at),
        destination=destination,
        # A person's own name for this run, or None for one nobody
        # named. See Run.label's docstring for why it lives here and
        # not on Recording.
        label=run.label,
    )


def input_info(recording: Recording | None) -> ManifestInput | None:
    if recording is None:
        return None
    provenance = _PROVENANCE_URL if recording.source_url else _PROVENANCE_LOCAL_FILE
    return ManifestInput(
        recording_id=recording.id,
        sha256=recording.content_sha256,
        duration_seconds=round(recording.duration_seconds, 3),
        media_format=recording.media_format,
        provenance=provenance,
        source_url=recording.source_url,
        source_title=recording.source_title,
    )


def environment_info(transcript: Transcript | None, choices: RunChoices) -> ManifestEnvironment:
    settings = get_settings()
    # The run's own choice, when there is one, is what was
    # requested. The machine's setting is only what a run that
    # chose nothing falls back to, same as engine.builtin._run_transcribe.
    requested = choices.hardware_profile or settings.hardware_profile
    # Transcript.hardware_profile is what transcription used.
    # Nothing today can make it diverge from the requested one, but the two
    # are recorded separately rather than assumed equal.
    used = transcript.hardware_profile if transcript is not None else requested
    # Same reasoning as hardware_profile_used above: read straight off the
    # Transcript, never recomputed. None when there is no Transcript yet,
    # or when it predates migration 0020. Never an invented
    # number standing in for either.
    cpu_threads = transcript.cpu_threads if transcript is not None else None
    num_workers = transcript.num_workers if transcript is not None else None
    return ManifestEnvironment(
        voxtrama_version=__version__,
        hardware_profile_requested=requested,
        hardware_profile_used=used,
        # Every profile runs on CPU in 0.1. A constant, not a
        # reading. voxtrama.diagnostics.machine detects a GPU for `doctor`,
        # a different concern from what a run used.
        device="cpu",
        cpu_threads=cpu_threads,
        num_workers=num_workers,
    )


def languages_info(transcript: Transcript | None) -> ManifestLanguages:
    """The three languages (interface, output, audio), honest about what is not wired up.

    Interface and output language selection do not exist anywhere in the
    engine yet, so both report `not_recorded`. Audio language is known once
    transcription has run: today the ASR always auto-detects it,
    so its provenance is `detected`, never a guess.
    """
    not_recorded = ManifestLanguage(value=None, provenance=LanguageProvenance.NOT_RECORDED)
    audio = (
        ManifestLanguage(value=transcript.language, provenance=LanguageProvenance.DETECTED)
        if transcript is not None
        else not_recorded
    )
    return ManifestLanguages(interface=not_recorded, audio=audio, output=not_recorded)


def workflow_info(run: Run, workflow: Workflow | None) -> ManifestWorkflow:
    """Name and version come from the Run: they are set before a workflow is
    even resolved, and a run that fails before resolving one (an unknown
    name, a cyclic graph) still needs a manifest. The hash needs
    the resolved definition, so it is None in exactly that case.
    """
    definition_sha256 = None if workflow is None else workflow_definition_sha256(workflow)
    return ManifestWorkflow(
        name=run.workflow_name, version=run.workflow_version, definition_sha256=definition_sha256
    )
