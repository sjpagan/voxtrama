"""Whether the installation can do its job right now, for the navbar.

The status row on the home page answered this for three claims, on
one page. The navbar answers it on every page, and for the four problems
that stop a job: Ollama not answering, the summary model
missing, the transcription model missing, the data folder unusable. Each
problem carries the one place in Settings where it is fixed, so the pill
is never a verdict without a way out.

Two readings feed it. diagnostics.readiness already reads the machine for
the transcription model and the data folder; this module reuses it rather
than asking the same questions a second time. The Ollama probe is the one
new reading, and the only one that touches the network, so a result is
kept for HEALTH_TTL_SECONDS: asking Ollama again on every page render
would put a network timeout in front of every click.

Nothing is probed when no summary model is configured: the answer is
already known ("no summary model chosen"), and asking the network to
confirm it would only cost time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.readiness import Readiness, read_readiness
from voxtrama.providers.ollama import OllamaProvider
from voxtrama.setup.generative_step import DEFAULT_PROBE_TIMEOUT_SECONDS, effective_ollama_url

HEALTH_TTL_SECONDS = 30.0

# Where each problem is fixed. Keys, not sentences: the text a person reads
# is components/header.html's, translated.
FIX_HREF = {
    "ollama-down": "/setup/model-ready",
    "summary-model-missing": "/models",
    "transcription-model-missing": "/models",
    "storage-unusable": "/setup/private-storage",
}


@dataclass(frozen=True)
class HealthProblem:
    """One thing that stops a job, and where it is fixed."""

    key: str
    href: str


@dataclass(frozen=True)
class Health:
    """Every problem found, most blocking first. Empty means all systems ready."""

    problems: tuple[HealthProblem, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


_cache: dict[tuple[object, ...], tuple[float, Health]] = {}


def _problem(key: str) -> HealthProblem:
    return HealthProblem(key=key, href=FIX_HREF[key])


def _summary_model_problem(settings: Settings) -> HealthProblem | None:
    """Ollama unreachable, or reachable without the configured model."""
    if settings.ollama_model is None:
        return _problem("summary-model-missing")
    auth = settings.ollama_auth.get_secret_value() if settings.ollama_auth else None
    provider = OllamaProvider(effective_ollama_url(settings), auth, DEFAULT_PROBE_TIMEOUT_SECONDS)
    probe = provider.probe()
    if not probe.reachable:
        return _problem("ollama-down")
    if settings.ollama_model not in {model.name for model in probe.models}:
        return _problem("summary-model-missing")
    return None


def _read(settings: Settings) -> Health:
    readiness = read_readiness(settings)
    problems = [_summary_model_problem(settings)]
    if readiness.models_ready.state is not Readiness.READY:
        problems.append(_problem("transcription-model-missing"))
    if readiness.private_storage.state is not Readiness.READY:
        problems.append(_problem("storage-unusable"))
    return Health(problems=tuple(problem for problem in problems if problem is not None))


def read_health(settings: Settings, *, now: float | None = None) -> Health:
    """The installation's health, read at most once every HEALTH_TTL_SECONDS per configuration."""
    key = (
        str(settings.data_dir),
        settings.ollama_url,
        settings.ollama_model,
        settings.hardware_profile,
    )
    moment = time.monotonic() if now is None else now
    cached = _cache.get(key)
    if cached is not None and moment - cached[0] < HEALTH_TTL_SECONDS:
        return cached[1]
    health = _read(settings)
    _cache[key] = (moment, health)
    return health
