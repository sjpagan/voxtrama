"""Public surface of the providers package.

OllamaProvider is deliberately not reexported here: text_provider_for is the
one supported way to get a TextProvider, so the local_only check in
providers.selection is never something a caller can route around by
importing the concrete class directly (same reason RQBackend stays out of
queue/__init__.py).
"""

from voxtrama.providers.base import (
    ModelProvenance,
    PrivacyViolation,
    ProviderCredentialsError,
    ProviderError,
    ProviderModelNotFoundError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderTransportError,
    TextProvider,
)
from voxtrama.providers.probe import GenerationSpeed, ProviderModel, ProviderProbe
from voxtrama.providers.selection import ProviderNotConfiguredError, text_provider_for

__all__ = [
    "TextProvider",
    "ModelProvenance",
    "ProviderError",
    "ProviderCredentialsError",
    "ProviderModelNotFoundError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "ProviderTransportError",
    "PrivacyViolation",
    "ProviderNotConfiguredError",
    "GenerationSpeed",
    "ProviderModel",
    "ProviderProbe",
    "text_provider_for",
]
