"""Builds the TextProvider a step will use, and stops local_only before it does.

Split out of providers.ollama so the place that decides "is this call
allowed" is not also the place that knows how to make an HTTP request. A
PrivacyViolation raised here comes before anything that could open a
connection is constructed.
"""

from __future__ import annotations

from voxtrama.config.settings import get_settings
from voxtrama.providers.base import PrivacyViolation, TextProvider
from voxtrama.providers.ollama import OllamaProvider
from voxtrama.providers.registry import LOCAL, provider_named
from voxtrama.workflow.skill import Privacy, Skill


class ProviderNotConfiguredError(RuntimeError):
    """A skill needs a TextProvider, and none is configured under the name asked for."""


def text_provider_for(
    skill: Skill, name: str | None = None, kept_local_by: str | None = None
) -> TextProvider:
    """The provider `skill` should call, or a PrivacyViolation before any of it runs.

    `name` is the run's choice among the configured providers.
    None is the installation's default. `kept_local_by` names the step
    or workflow that declared `local_only` above a skill that did not.
    Order matters: local or remote is read off the provider's URL
    first, and the privacy check happens before OllamaProvider is
    constructed: it "fails before the first network call".
    """
    settings = get_settings()
    provider = provider_named(settings, name)
    if provider is None:
        wanted = f"no provider named {name!r}" if name else "VOXTRAMA_OLLAMA_URL is not set"
        raise ProviderNotConfiguredError(wanted)
    if (skill.privacy == Privacy.LOCAL_ONLY or kept_local_by) and provider.locality != LOCAL:
        who = kept_local_by or f"{skill.name}@{skill.version}"
        raise PrivacyViolation(f"{who} is local_only, and provider {provider.name} is remote")
    auth = provider.auth.get_secret_value() if provider.auth else None
    return OllamaProvider(provider.url, auth, settings.provider_timeout_seconds)
