"""diagnostics.health: the navbar's pill, and where each problem is fixed.

The Ollama probe is replaced by a stub: these tests are about which problem
the pill names and where it sends a person, not about the network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.ollama_provider import reachable_probe

from voxtrama.config.settings import Settings
from voxtrama.diagnostics import health as health_module
from voxtrama.diagnostics.readiness_state import (
    LocalProcessingCheck,
    ModelsReadyCheck,
    PrivateStorageCheck,
    Readiness,
    ReadinessReport,
)
from voxtrama.providers.probe import ProviderProbe

_READY = Readiness.READY


def _report(models: Readiness = _READY, storage: Readiness = _READY) -> ReadinessReport:
    return ReadinessReport(
        local_processing=LocalProcessingCheck(state=_READY, reason="", hardware_profile="pro"),
        models_ready=ModelsReadyCheck(state=models, reason="", model="medium"),
        private_storage=PrivateStorageCheck(state=storage, reason="", free_disk_bytes=None),
    )


def _stub(monkeypatch: pytest.MonkeyPatch, report: ReadinessReport, probe: ProviderProbe) -> list:
    calls: list = []
    monkeypatch.setattr(health_module, "read_readiness", lambda settings: report)

    class _Provider:
        def __init__(self, url: str, auth: object, timeout: float) -> None:
            calls.append(timeout)

        def probe(self) -> ProviderProbe:
            return probe

    monkeypatch.setattr(health_module, "OllamaProvider", _Provider)
    health_module._cache.clear()
    return calls


def _unreachable() -> ProviderProbe:
    return ProviderProbe(
        reachable=False, latency_seconds=None, version=None, models=(), error="refused"
    )


def test_everything_ready_means_no_problem(tmp_path: Path, monkeypatch) -> None:
    _stub(monkeypatch, _report(), reachable_probe("llama3.1:8b"))
    health = health_module.read_health(Settings(data_dir=tmp_path, ollama_model="llama3.1:8b"))

    assert health.ok


def test_ollama_down_comes_first_and_leads_to_model_ready(tmp_path: Path, monkeypatch) -> None:
    _stub(monkeypatch, _report(models=Readiness.NOT_READY), _unreachable())
    health = health_module.read_health(Settings(data_dir=tmp_path, ollama_model="llama3.1:8b"))

    assert [p.key for p in health.problems] == ["ollama-down", "transcription-model-missing"]
    assert health.problems[0].href == "/setup/model-ready"
    assert health.problems[1].href == "/models"


def test_no_summary_model_is_known_without_asking_the_network(tmp_path: Path, monkeypatch) -> None:
    calls = _stub(monkeypatch, _report(), reachable_probe())
    health = health_module.read_health(Settings(data_dir=tmp_path))

    assert [p.key for p in health.problems] == ["summary-model-missing"]
    assert calls == []


def test_a_model_ollama_does_not_have_is_missing(tmp_path: Path, monkeypatch) -> None:
    _stub(monkeypatch, _report(), reachable_probe("gemma3:4b"))
    health = health_module.read_health(Settings(data_dir=tmp_path, ollama_model="llama3.1:8b"))

    assert [p.key for p in health.problems] == ["summary-model-missing"]


def test_an_unusable_data_folder_leads_to_private_storage(tmp_path: Path, monkeypatch) -> None:
    _stub(monkeypatch, _report(storage=Readiness.UNKNOWN), reachable_probe("m"))
    health = health_module.read_health(Settings(data_dir=tmp_path, ollama_model="m"))

    assert [(p.key, p.href) for p in health.problems] == [
        ("storage-unusable", "/setup/private-storage")
    ]


def test_the_reading_is_kept_for_the_ttl_then_read_again(tmp_path: Path, monkeypatch) -> None:
    calls = _stub(monkeypatch, _report(), reachable_probe("m"))
    settings = Settings(data_dir=tmp_path, ollama_model="m")

    health_module.read_health(settings, now=100.0)
    health_module.read_health(settings, now=100.0 + health_module.HEALTH_TTL_SECONDS - 1)
    assert len(calls) == 1

    health_module.read_health(settings, now=100.0 + health_module.HEALTH_TTL_SECONDS + 1)
    assert len(calls) == 2
