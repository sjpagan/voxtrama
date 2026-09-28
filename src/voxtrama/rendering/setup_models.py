"""What the "Model ready" step's list of Ollama models shows.

Turns providers.probe.ProviderModel (this project's reading of
/api/tags, already trusted by `doctor`) into the one string
pages/setup_model_ready.html needs beyond the name: a human-readable
size, or "unknown" when the provider declared none (diagnostics'
"unknown, never a plausible zero" rule, extended to a provider's
optional field). The licence fields pass setup.licences.ModelLicence
straight through, already classified there (a presenter formats,
it does not decide what counts as permissive). A model whose facts could
not be read comes back with no SPDX id, not permissive, no text: the
same shape a "licence unknown" row needs.
"""

from __future__ import annotations

from dataclasses import dataclass

from voxtrama.humanize import human_bytes
from voxtrama.providers.probe import ProviderModel
from voxtrama.setup.licences import ModelLicence


@dataclass(frozen=True)
class ModelRowView:
    """One row of the Ollama model list, exactly as the template shows it."""

    name: str
    size_label: str
    licence_spdx: str | None
    licence_permissive: bool
    licence_text: str | None


def model_row_views(
    models: tuple[ProviderModel, ...], licences_by_model: dict[str, ModelLicence]
) -> list[ModelRowView]:
    return [_row(model, licences_by_model.get(model.name)) for model in models]


def _row(model: ProviderModel, licence: ModelLicence | None) -> ModelRowView:
    size_label = human_bytes(model.size_bytes) if model.size_bytes else "unknown"
    return ModelRowView(
        name=model.name,
        size_label=size_label,
        licence_spdx=licence.spdx if licence else None,
        licence_permissive=licence.permissive if licence else False,
        licence_text=licence.text if licence else None,
    )
