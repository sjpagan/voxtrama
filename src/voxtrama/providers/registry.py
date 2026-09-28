"""The providers a run can choose among, by name.

A run names one of the providers configured on the machine, never a URL:
which hosts the transcript may reach stays the installer's decision.
With no registry configured, the pair ollama_url/ollama_auth is the
provider called `default`, so no installation has to be rewritten. Each
provider is local or remote, read off its URL the way the privacy check
always has (providers.ollama.classify_host).
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import SecretStr

from voxtrama.config.settings import Settings
from voxtrama.providers.ollama import classify_host

DEFAULT = "default"
LOCAL = "local"
REMOTE = "remote"


@dataclass(frozen=True)
class NamedProvider:
    """A configured provider: its name, where it answers, its credential."""

    name: str
    url: str
    auth: SecretStr | None

    @property
    def locality(self) -> str:
        """`local` or `remote`, as read by the manifest and the privacy rule."""
        return LOCAL if classify_host(self.url)[1] else REMOTE


def configured_providers(settings: Settings) -> dict[str, NamedProvider]:
    """Every provider a run may name, in the order they were configured."""
    if settings.providers:
        return {
            name: NamedProvider(name, config.url, config.auth)
            for name, config in settings.providers.items()
        }
    if settings.ollama_url:
        return {DEFAULT: NamedProvider(DEFAULT, settings.ollama_url, settings.ollama_auth)}
    return {}


def provider_named(settings: Settings, name: str | None) -> NamedProvider | None:
    """The provider `name` names; with no name, `default` or else the first one."""
    providers = configured_providers(settings)
    if name is not None:
        return providers.get(name)
    return providers.get(DEFAULT) or next(iter(providers.values()), None)
