"""Which accelerator torch reports, without depending on what this machine has.

torch is injected through sys.modules rather than mocked at the call
site: detect_accelerator() imports it locally, so replacing the entry
import picks up is the isolation that matches how the function is
written.
"""

from __future__ import annotations

import sys
import types

import pytest

from voxtrama.diagnostics.accelerator import detect_accelerator


def _fake_torch(*, cuda: bool, mps: bool) -> types.ModuleType:
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: cuda)
    torch.backends = types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: mps))
    return torch


def test_cuda_is_reported_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=True, mps=False))

    assert detect_accelerator() == "cuda"


def test_mps_is_reported_when_cuda_is_not_the_m_series_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reported case: torch.cuda.is_available() is False on every M-series Mac."""
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=False, mps=True))

    assert detect_accelerator() == "mps"


def test_neither_accelerator_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=False, mps=False))

    assert detect_accelerator() is None


def test_torch_not_installed_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", None)

    assert detect_accelerator() is None


def test_a_probe_that_raises_is_treated_as_no_accelerator_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch = _fake_torch(cuda=False, mps=False)
    torch.cuda.is_available = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    monkeypatch.setitem(sys.modules, "torch", torch)

    assert detect_accelerator() is None
