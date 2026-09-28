"""One configured text provider, as Settings.providers holds it.

A name maps to a URL and, when the server needs one, a credential. The
credential is a SecretStr: its repr is "**********", so it
never reaches a log or a manifest by being printed.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, SecretStr


def _no_credential_in_url(url: str) -> str:
    """Refuse `https://user:secret@host`: the credential goes in `auth`.

    A credential written into the address was
    shown on Data & privacy and Settings, copied into voxtrama.toml, and
    never worked anyway (urllib reads the secret as a port). The error
    names neither the address nor the secret (hide_input_in_errors).
    """
    parts = urlsplit(url)
    if parts.username is not None or parts.password is not None:
        raise ValueError(
            "the address carries a credential: set it in auth (VOXTRAMA_OLLAMA_AUTH) instead"
        )
    return url


ProviderUrl = Annotated[str, AfterValidator(_no_credential_in_url)]


class ProviderConfig(BaseModel):
    """A provider a run can name: where it answers, and its credential if any."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    url: ProviderUrl
    auth: SecretStr | None = None
