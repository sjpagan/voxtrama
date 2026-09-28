"""What step 3 ("Model ready") needs beyond a plain Ollama probe.

Wraps providers.ollama.OllamaProvider and providers.ollama_show for the
two things this step does that `doctor` does not: list the configured
Ollama's models and read each one's /api/show facts (context length,
capped in setup.context_cap, and licence text), then read
context_length again on step 4 for the selected model. An unreachable or
unconfigured Ollama is not a fault here: the step has nothing to offer,
as in `doctor`'s "not configured" case.

With no `VOXTRAMA_OLLAMA_URL` set, this step also tries the standard
local address. No decision should be required before the first success,
so a running Ollama must be found without an environment variable.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.config.settings import Settings
from voxtrama.providers.ollama import OllamaProvider, auth_header, classify_host
from voxtrama.providers.ollama_show import ModelFacts, read_model_facts
from voxtrama.providers.probe import ProviderModel
from voxtrama.setup.context_cap import resolve_num_ctx_cap

# Inside this project's container, "localhost" names the container, not
# the machine running Ollama. host.docker.internal is the address that
# reaches it: Docker Desktop (macOS, Windows) resolves that name to the
# host automatically, with no extra_hosts entry. providers.ollama's
# LOCAL_HOSTS already relies on the same name to classify the worker's
# calls as local. Plain Docker Engine on Linux needs it added by hand
# (`extra_hosts: ["host.docker.internal:host-gateway"]`, Docker 20.10+),
# and compose.yaml does not add it: there this probe finds nothing until
# someone does. Nothing here closes that gap.
DEFAULT_OLLAMA_URL = "http://host.docker.internal:11434"
# What a person who ran `ollama serve` recognises: the standard address,
# never the container-only name it resolves through. The setup pages hide
# a container-only detail (the data directory) the same way, for the same
# reason.
DEFAULT_OLLAMA_LABEL = "localhost:11434"
# Short: provider_timeout_seconds (120s) is sized for a real generation
# call, and waiting that long on every visit to this step would turn
# "nothing is there" into a half-minute stall, a wait a first success
# must not require.
DEFAULT_PROBE_TIMEOUT_SECONDS = 1.5


@dataclass(frozen=True)
class GenerativeProviderState:
    """What the "Add a local generative model" panel needs to show."""

    configured: bool
    reachable: bool
    host: str | None
    models: tuple[ProviderModel, ...]


def probe_generative_provider(settings: Settings) -> GenerativeProviderState:
    """Reachability and models of the configured Ollama, never raising.

    With nothing configured, a quick try at the standard address
    (DEFAULT_OLLAMA_URL) replaces the previous silent "not configured".
    Only a *successful* try counts as configured. A failed one still
    leaves nothing to blame on a missing setting.
    """
    if settings.ollama_url is None:
        return _probe_default(settings)
    host, _ = classify_host(settings.ollama_url)
    provider = _provider(settings.ollama_url, settings)
    probe = provider.probe()
    return GenerativeProviderState(
        configured=True, reachable=probe.reachable, host=host, models=probe.models
    )


def _probe_default(settings: Settings) -> GenerativeProviderState:
    provider = _provider(DEFAULT_OLLAMA_URL, settings, DEFAULT_PROBE_TIMEOUT_SECONDS)
    probe = provider.probe()
    if not probe.reachable:
        return GenerativeProviderState(configured=False, reachable=False, host=None, models=())
    return GenerativeProviderState(
        configured=True, reachable=True, host=DEFAULT_OLLAMA_LABEL, models=probe.models
    )


def effective_ollama_url(settings: Settings) -> str:
    """The address this step probed: settings.ollama_url, or the standard
    local one (DEFAULT_OLLAMA_URL) when nothing is configured.

    Also the address the guided setup records once a model is chosen
    (setup.finish.installation_config_from_choices). Whichever of these two
    addresses step 3 listed that model from is the one to write down, not
    a third guess.
    """
    return settings.ollama_url or DEFAULT_OLLAMA_URL


def num_ctx_cap_for(settings: Settings, model: str) -> int | None:
    """`model`'s num_ctx ceiling, or None if unreadable.

    Reached only after step 3 listed `model` (from the configured Ollama
    or from the standard address), so the same address is tried
    again here at the normal provider_timeout_seconds. It was just proven
    reachable, so this is not the guess DEFAULT_PROBE_TIMEOUT_SECONDS
    bounds. A separate request (step 4): step 3's model_facts_for
    already read this model once for its licence, but that reading does
    not survive between two requests, so this one asks again.
    """
    facts = read_model_facts(*_show_args(settings, model))
    return resolve_num_ctx_cap(facts.context_length)


def model_facts_for(settings: Settings, models: tuple[ProviderModel, ...]) -> dict[str, ModelFacts]:
    """Every listed model's /api/show reading, once each.

    Step 3 shows a licence next to every installed model, not only the one
    selected (the asterisk marks each row), so unlike
    num_ctx_cap_for this reads every model in `models`. Still one request
    per model, never two for the one that ends up selected: the caller
    reuses this dict's context_length instead of asking num_ctx_cap_for
    again.
    """
    return {model.name: read_model_facts(*_show_args(settings, model.name)) for model in models}


def _show_args(settings: Settings, model: str) -> tuple[str, str, str, dict[str, str], float]:
    url = effective_ollama_url(settings)
    host, _ = classify_host(url)
    auth = settings.ollama_auth.get_secret_value() if settings.ollama_auth else None
    headers = auth_header(auth, url)
    return url, host, model, headers, settings.provider_timeout_seconds


def _provider(url: str, settings: Settings, timeout: float | None = None) -> OllamaProvider:
    auth = settings.ollama_auth.get_secret_value() if settings.ollama_auth else None
    effective_timeout = timeout if timeout is not None else settings.provider_timeout_seconds
    return OllamaProvider(url, auth, effective_timeout)
