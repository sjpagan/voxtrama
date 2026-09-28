"""select_tuning against real and synthetic MachineReports.

MachineReports are built by hand throughout: this must decide correctly
without the machine it is deciding for. That is what a tuning file
replacing a hardcoded device= is for (see tuning/__init__.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voxtrama.config.settings import get_settings
from voxtrama.diagnostics.machine import MachineReport
from voxtrama.tuning.errors import TuningConflictError, TuningValidationError
from voxtrama.tuning.selector import select_tuning


def _machine(
    architecture: str, accelerator: str | None = None, unified_memory: bool = False
) -> MachineReport:
    return MachineReport(
        platform="test",
        architecture=architecture,
        cpu_count=8,
        performance_cores=None,
        efficiency_cores=None,
        cpu_brand=None,
        total_memory_bytes=16 * 1024**3,
        unified_memory=unified_memory,
        free_disk_bytes=100 * 1024**3,
        gpu_available=accelerator is not None,
        accelerator=accelerator,
        in_container=False,
    )


def test_apple_silicon_picks_its_own_file() -> None:
    tuning = select_tuning(_machine("arm64", accelerator="mps", unified_memory=True))
    assert tuning.name == "apple-silicon"


def test_x86_with_cuda_picks_its_own_file() -> None:
    tuning = select_tuning(_machine("x86_64", accelerator="cuda"))
    assert tuning.name == "x86-cuda"


def test_x86_with_no_accelerator_picks_its_own_file() -> None:
    tuning = select_tuning(_machine("x86_64", accelerator=None))
    assert tuning.name == "x86-no-accelerator"


def test_an_unrecognised_machine_falls_back_to_generic() -> None:
    tuning = select_tuning(_machine("aarch64-linux", accelerator=None))
    assert tuning.name == "generic"


def test_a_tuning_file_in_the_data_dir_wins_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file in the data dir overrides a bundled one by name, in this folder too."""
    override_dir = tmp_path / "tuning"
    override_dir.mkdir()
    (override_dir / "generic.yaml").write_text(_GENERIC_OVERRIDE)
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    tuning = select_tuning(_machine("aarch64-linux", accelerator=None))

    assert tuning.name == "generic-override"


def test_a_malformed_override_fails_loudly_instead_of_falling_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override_dir = tmp_path / "tuning"
    override_dir.mkdir()
    (override_dir / "generic.yaml").write_text("name: broken\napplies_to: {}\n")
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    with pytest.raises(TuningValidationError) as excinfo:
        select_tuning(_machine("aarch64-linux", accelerator=None))
    assert "generic.yaml" in str(excinfo.value)


def test_two_tied_files_raise_a_conflict_naming_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override_dir = tmp_path / "tuning"
    override_dir.mkdir()
    (override_dir / "one.yaml").write_text(_tied_file("first"))
    (override_dir / "two.yaml").write_text(_tied_file("second"))
    monkeypatch.setenv("VOXTRAMA_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    with pytest.raises(TuningConflictError) as excinfo:
        select_tuning(_machine("test-arch", accelerator=None))
    assert "one.yaml" in str(excinfo.value)
    assert "two.yaml" in str(excinfo.value)


_GENERIC_OVERRIDE = """
name: generic-override
description: a data-dir copy of generic.yaml
applies_to: {}
asr:
  device: cpu
  profiles:
    low: {model_size: small, compute_type: int8}
    base: {model_size: medium, compute_type: int8}
    high: {model_size: large-v3, compute_type: int8}
diarization:
  device: cpu
chunking:
  parallel_chunks: 1
  cores_per_chunk: 1
  memory: {recommended_gib: 16, warning: "test"}
generative:
  memory: {recommended_gib: 16, warning: "test"}
  timeout_seconds: 1800
"""


def _tied_file(name: str) -> str:
    return f"""
name: {name}
description: two files tied at one declared condition
applies_to:
  architecture: test-arch
asr:
  device: cpu
  profiles:
    low: {{model_size: small, compute_type: int8}}
    base: {{model_size: medium, compute_type: int8}}
    high: {{model_size: large-v3, compute_type: int8}}
diarization:
  device: cpu
chunking:
  parallel_chunks: 1
  cores_per_chunk: 1
  memory: {{recommended_gib: 16, warning: "test"}}
generative:
  memory: {{recommended_gib: 16, warning: "test"}}
  timeout_seconds: 1800
"""
