"""What the new-job form starts from: this installation's own settings.

The principle: «Uses the settings of this
installation unless changed». The form shows these values with a
`Default` tag. A field the person moves off its default turns `Changed`,
and only a changed field becomes the job's own choice (RunChoices), the
same "None means chose nothing" reading every choice gets. The
page and POST /jobs both read defaults from here, so the value a form
calls default is the value the server compares against.

Cores and parallel chunks fall back to this machine's own tuning proposal
when Settings names none, as transcribe() does
(transcription.resources), so the form never shows a number the run would
not have used.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.machine import read_machine
from voxtrama.providers.registry import configured_providers, provider_named
from voxtrama.setup.installation import read_installation_config
from voxtrama.transcription.profiles import PROFILES
from voxtrama.transcription.resources import resolve_engine_resources


@dataclass(frozen=True)
class JobDefaults:
    """The installation's value for every field of the new-job form."""

    hardware_profile: str
    parallel_chunks: int
    cores_per_chunk: int
    generative_model: str | None
    summary_detail: int
    pause_merge_seconds: float
    machine_cores: int | None
    # The recap's language: "" is «Same as the audio»; the
    # new-job form replaces it with the browser's own language.
    output_language: str = ""
    # The job's own limit in days ("" none) and the installation's,
    # which the job can only shorten.
    retention_days: str = ""
    installation_retention_days: int | None = None
    # The providers a job can name, (name, local|remote), and the default.
    providers: tuple[tuple[str, str], ...] = ()
    provider: str = ""


def job_defaults(settings: Settings) -> JobDefaults:
    """The defaults the form shows and POST /jobs compares a submission against."""
    cores, parallel = resolve_engine_resources(
        settings.data_dir, settings.cores_per_chunk, settings.parallel_chunks
    )
    return JobDefaults(
        hardware_profile=settings.hardware_profile,
        parallel_chunks=parallel,
        cores_per_chunk=cores,
        generative_model=settings.ollama_model,
        summary_detail=settings.summary_detail,
        pause_merge_seconds=settings.pause_merge_seconds,
        machine_cores=read_machine(settings.data_dir).cpu_count,
        installation_retention_days=settings.retention_days,
        providers=tuple((p.name, p.locality) for p in configured_providers(settings).values()),
        provider=getattr(provider_named(settings, None), "name", ""),
    )


def transcription_models() -> list[tuple[str, str]]:
    """(hardware profile, Whisper model size) for the form's model select."""
    return [(profile, model.model_size) for profile, model in PROFILES.items()]


def summary_models(settings: Settings) -> list[str]:
    """The configured model plus every model the setup measured; no network."""
    config = read_installation_config(settings.data_dir)
    measured = sorted(config.model_context_limits) if config is not None else []
    configured = [settings.ollama_model] if settings.ollama_model else []
    return configured + [name for name in measured if name not in configured]
