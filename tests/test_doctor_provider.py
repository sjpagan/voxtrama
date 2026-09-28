"""What `voxtrama doctor` prints about the generative provider.

The double here stands for OllamaProvider itself, same idea as
test_providers_selection.py's _FakeOllamaProvider: cli.commands.doctor_provider
only calls .probe() and .measure_generation(), so a fake answering those two
is enough to drive print_provider() without a socket.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

import voxtrama.cli.commands.doctor_provider as doctor_provider
from voxtrama.cli.commands.doctor_provider import print_provider
from voxtrama.config.settings import Settings
from voxtrama.providers.probe import GenerationSpeed, ProviderModel, ProviderProbe

_MODELS = (
    ProviderModel(name="gemma3:4b", size_bytes=3_338_801_804),
    ProviderModel(name="qwen3:4b", size_bytes=2_497_293_931),
)
_PROBE = ProviderProbe(
    reachable=True, latency_seconds=0.01, version="0.34.2", models=_MODELS, error=None
)
_SPEED = GenerationSpeed(
    model="qwen3:4b",
    tokens=17,
    tokens_per_second=18.47,
    load_seconds=5.58,
    wall_seconds=6.73,
    source="provider timings",
)


def _fake_provider_class(probe: ProviderProbe, speed: GenerationSpeed) -> type:
    """A stand-in for OllamaProvider that records which model it was asked to time."""

    class _FakeOllamaProvider:
        measured_models: ClassVar[list[str]] = []

        def __init__(self, url: str, auth: str | None, timeout: float) -> None:
            pass

        def probe(self) -> ProviderProbe:
            return probe

        def measure_generation(self, model: str) -> GenerationSpeed:
            type(self).measured_models.append(model)
            return speed

    return _FakeOllamaProvider


def test_no_ollama_url_says_not_configured_and_how_to_set_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    print_provider(Settings(ollama_url=None), measure=True)

    output = capsys.readouterr().out
    assert "no generative provider is configured" in output
    assert "VOXTRAMA_OLLAMA_URL" in output


def test_the_smallest_present_model_is_measured_and_named(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """qwen3:4b (2.3 GiB) is smaller than gemma3:4b (3.1 GiB)."""
    fake_cls = _fake_provider_class(_PROBE, _SPEED)
    monkeypatch.setattr(doctor_provider, "OllamaProvider", fake_cls)

    print_provider(Settings(ollama_url="http://127.0.0.1:11434"), measure=True)

    output = capsys.readouterr().out
    assert fake_cls.measured_models == ["qwen3:4b"]
    assert "qwen3:4b" in output
    assert "18.5 tokens/s" in output
    assert "5.6 s" in output


def test_no_measure_skips_generation_but_reports_the_rest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The double records that measure_generation was never called."""
    fake_cls = _fake_provider_class(_PROBE, _SPEED)
    monkeypatch.setattr(doctor_provider, "OllamaProvider", fake_cls)

    print_provider(Settings(ollama_url="http://127.0.0.1:11434"), measure=False)

    output = capsys.readouterr().out
    assert fake_cls.measured_models == []
    assert "skipped (--no-measure)" in output
    assert "0.34.2" in output
    assert "qwen3:4b" in output
