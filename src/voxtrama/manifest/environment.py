"""ManifestEnvironment: which hardware a run asked for, and which it used.

Split from schema.py to keep that file under the project's size limit, the
same reason ManifestChoices lives in choices.py and ManifestEvidence in
evidence.py rather than there.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from voxtrama.config.settings import Settings
from voxtrama.providers.registry import provider_named


class ManifestProvider(BaseModel):
    """Where the generative steps ran: the name, local or remote.

    Never the host: a manifest can be exported, and a host would give away
    the network of whoever produced it. The locality is what proves that
    `local_only` was honoured.
    """

    model_config = ConfigDict(extra="forbid")
    name: str
    locality: str


class ManifestEnvironment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voxtrama_version: str
    hardware_profile_requested: str
    hardware_profile_used: str
    device: str
    # The cpu_threads/num_workers transcription.asr's transcribe()
    # handed WhisperModel: resolve_engine_
    # resources's own return value, which can differ from the requested
    # Settings.cores_per_chunk/.parallel_chunks when a run fell back to
    # this machine's own tuning proposal. Both None when there is no
    # Transcript yet, or when it was written before migration 0020 gave it
    # these two columns. Never an invented number standing in for either.
    cpu_threads: int | None
    num_workers: int | None
    # None for a run no generative step has called a provider for.
    provider: ManifestProvider | None = None


def provider_info(settings: Settings, chosen: str | None, called: bool) -> ManifestProvider | None:
    """The provider the run's generative steps called, when any did, even in vain."""
    if not called:
        return None
    provider = provider_named(settings, chosen)
    return ManifestProvider(name=provider.name, locality=provider.locality) if provider else None
