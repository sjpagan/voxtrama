"""The slim settings line under a concluded job's title.

«Meeting decisions · Whisper small · llama3.1:8b · Detail 4/5 · 2×8
cores · Context ✓»: what the job ran with, read from its manifest. The
models come from steps[] (what really ran), the cores from
environment, the detail and the context from choices. A value the
manifest does not carry is left out, not guessed. The exception is the
summary detail: when the job did not choose one, the run used the
installation default (engine.summary_detail). A transcript read in
windows adds «5 windows of ~12k characters».
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.manifest.schema import Manifest
from voxtrama.rendering.job_regenerate import RegenerateForm

_NOT_GENERATIVE = {"transcribe", "diarize"}


@dataclass(frozen=True)
class SettingsLine:
    workflow: str
    transcription_model: str | None
    summary_model: str | None
    summary_detail: int | None
    cores: str | None
    has_context: bool
    # How many windows the longest-read generative step used, only
    # when the transcript was split: the split is visible.
    windows: int | None = None
    # The context was deduced, not declared, shown as such.
    deduced_context: str | None = None


def _model_of(manifest: Manifest, skill: str) -> str | None:
    return next((step.model for step in manifest.steps if step.skill == skill and step.model), None)


def _summary_model(manifest: Manifest) -> str | None:
    return next(
        (step.model for step in manifest.steps if step.skill not in _NOT_GENERATIVE and step.model),
        None,
    )


def _windows(manifest: Manifest) -> int | None:
    counts = [step.transcript_windows or 1 for step in manifest.steps]
    most = max(counts, default=1)
    return most if most > 1 else None


def settings_line(
    manifest: Manifest | None, workflow_title: str, default_detail: int
) -> SettingsLine:
    """The line for one job. Only the workflow when there is no manifest."""
    if manifest is None:
        return SettingsLine(workflow_title, None, None, None, None, False)
    environment = manifest.environment
    cores = None
    if environment.num_workers and environment.cpu_threads:
        cores = f"{environment.num_workers}×{environment.cpu_threads}"
    summarizes = any(step.skill == "summarize" for step in manifest.steps)
    detail = manifest.choices.summary_detail or default_detail
    return SettingsLine(
        workflow=workflow_title,
        transcription_model=_model_of(manifest, "transcribe"),
        summary_model=_summary_model(manifest),
        summary_detail=detail if summarizes else None,
        cores=cores,
        has_context=bool(manifest.choices.context),
        windows=_windows(manifest),
        deduced_context=manifest.choices.context_deduced,
    )


@dataclass(frozen=True)
class JobHead:
    """The job view's head in any state: the line, and «Regenerate job» when it applies."""

    settings: SettingsLine
    regenerate: RegenerateForm | None
    # How long the job's data stays, and the date it goes once the job
    # is over (formatted for the reader). None when no limit applies.
    retention_days: int | None = None
    deletes_on: str | None = None
