"""A stand-in for providers.ollama.OllamaProvider: same constructor
shape, a `.probe()` that returns a canned ProviderProbe instead of
touching a real socket. Shared by every test that exercises setup.
generative_step's default-address probe without depending on what is or
is not listening on this machine.

`reachable_probe` and `stub_model_facts` round this out for
setup.generative_step.model_facts_for's own /api/show read: a reachable
probe naming whichever models a test wants, and a canned lookup replacing
the read itself so no test needs a real /api/show fake per model.
"""

from __future__ import annotations

import pytest

from voxtrama.providers.ollama_show import ModelFacts
from voxtrama.providers.probe import ProviderModel, ProviderProbe


def fake_ollama_provider(probe: ProviderProbe) -> type:
    class _Provider:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def probe(self) -> ProviderProbe:
            return probe

    return _Provider


def reachable_probe(*names: str) -> ProviderProbe:
    """A reachable ProviderProbe listing one ProviderModel per name, no size."""
    models = tuple(ProviderModel(name=name, size_bytes=None) for name in names)
    return ProviderProbe(
        reachable=True, latency_seconds=0.02, version="0.34.3", models=models, error=None
    )


def stub_model_facts(
    monkeypatch: pytest.MonkeyPatch, generative_step: object, facts_by_name: dict[str, ModelFacts]
) -> list[str]:
    """Replaces `generative_step.read_model_facts` with a canned lookup,
    recording every model name it was asked for: the "one request per
    model" count the web layer's own contract makes.
    """
    calls: list[str] = []

    def _fake(
        url: str, host: str, model: str, headers: dict[str, str], timeout: float
    ) -> ModelFacts:
        calls.append(model)
        return facts_by_name[model]

    monkeypatch.setattr(generative_step, "read_model_facts", _fake)
    return calls
