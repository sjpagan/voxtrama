"""Core-class and processor-name reading, isolated from the machine running the tests.

This machine is an Intel Xeon (measured 2026-09-24: perflevel0 answers,
perflevel1 comes back empty). The case that matters, an Apple Silicon
split into performance and efficiency cores, has to be simulated.
"""

from __future__ import annotations

import subprocess

import pytest

from voxtrama.diagnostics.cpu_topology import (
    has_unified_memory,
    read_core_topology,
    read_cpu_brand,
)


def _sysctl_stub(values: dict[str, str]):
    """A fake `subprocess.run` answering only the sysctl keys given, others empty."""

    def run(cmd, **kwargs):
        value = values.get(cmd[-1], "")
        return subprocess.CompletedProcess(cmd, 0 if value else 1, stdout=value, stderr="")

    return run


def test_two_perflevels_are_split_into_performance_and_efficiency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "voxtrama.diagnostics.cpu_topology.subprocess.run",
        _sysctl_stub({"hw.perflevel0.logicalcpu": "8", "hw.perflevel1.logicalcpu": "4"}),
    )

    assert read_core_topology() == (8, 4)


def test_a_homogeneous_mac_answers_one_class_and_gets_no_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This machine's own shape: perflevel1 comes back blank, not missing."""
    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "voxtrama.diagnostics.cpu_topology.subprocess.run",
        _sysctl_stub({"hw.perflevel0.logicalcpu": "20"}),
    )

    assert read_core_topology() == (None, None)


def test_sysctl_missing_outright_is_also_no_split(monkeypatch: pytest.MonkeyPatch) -> None:
    """Linux: the command does not exist at all. A different reason, the same (None, None)."""
    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.platform.system", lambda: "Darwin")

    def missing(cmd, **kwargs):
        raise OSError("sysctl: command not found")

    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.subprocess.run", missing)

    assert read_core_topology() == (None, None)


def test_non_darwin_never_probes_for_a_split(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.platform.system", lambda: "Linux")

    assert read_core_topology() == (None, None)


def test_cpu_brand_from_sysctl_on_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "voxtrama.diagnostics.cpu_topology.subprocess.run",
        _sysctl_stub({"machdep.cpu.brand_string": "Apple M2 Pro"}),
    )

    assert read_cpu_brand() == "Apple M2 Pro"


def test_cpu_brand_from_proc_cpuinfo_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "voxtrama.diagnostics.cpu_topology.Path.read_text",
        lambda self: "processor\t: 0\nmodel name\t: AMD Ryzen 9\nflags\t: fpu\n",
    )

    assert read_cpu_brand() == "AMD Ryzen 9"


def test_cpu_brand_unreadable_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.platform.system", lambda: "Linux")

    def missing(self):
        raise OSError("no such file")

    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.Path.read_text", missing)

    assert read_cpu_brand() is None


def test_unified_memory_is_true_only_on_apple_silicon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.platform.system", lambda: "Darwin")

    assert has_unified_memory("arm64") is True
    assert has_unified_memory("x86_64") is False


def test_unified_memory_is_false_off_darwin_even_on_arm64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.cpu_topology.platform.system", lambda: "Linux")

    assert has_unified_memory("arm64") is False
