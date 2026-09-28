"""Unit tests for engine.resource_choice: cores_per_chunk/parallel_chunks vs the machine.

Monkeypatches diagnostics.machine.read_machine the same way
tests/test_transcription_asr_resources.py does: where it is defined, not
where it is used, since resource_choice imports the module itself.
"""

from __future__ import annotations

import pytest

from voxtrama.diagnostics.machine import MachineReport
from voxtrama.engine.resource_choice import check_resource_choice
from voxtrama.workflow.choices import RunChoices


def _machine(cpu_count: int | None) -> MachineReport:
    return MachineReport(
        platform="test",
        architecture="x86_64",
        cpu_count=cpu_count,
        performance_cores=None,
        efficiency_cores=None,
        cpu_brand=None,
        total_memory_bytes=None,
        unified_memory=False,
        free_disk_bytes=None,
        gpu_available=False,
        accelerator=None,
        in_container=False,
    )


def test_asking_for_more_cores_than_the_machine_has_is_rejected_naming_the_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.machine.read_machine", lambda data_dir: _machine(20))

    rejections = check_resource_choice(RunChoices(cores_per_chunk=32))

    assert len(rejections) == 1
    assert rejections[0].field == "cores_per_chunk"
    assert rejections[0].value == "32"
    assert "available_cores 20" in rejections[0].constraint


def test_both_fields_over_budget_are_rejected_in_field_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.machine.read_machine", lambda data_dir: _machine(4))

    rejections = check_resource_choice(RunChoices(cores_per_chunk=8, parallel_chunks=9))

    assert [r.field for r in rejections] == ["cores_per_chunk", "parallel_chunks"]


def test_a_choice_within_budget_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxtrama.diagnostics.machine.read_machine", lambda data_dir: _machine(20))

    assert check_resource_choice(RunChoices(cores_per_chunk=4, parallel_chunks=2)) == []


def test_unknown_hardware_caps_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "voxtrama.diagnostics.machine.read_machine", lambda data_dir: _machine(None)
    )

    assert check_resource_choice(RunChoices(cores_per_chunk=999)) == []


def test_an_empty_choice_never_reads_the_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(data_dir):
        raise AssertionError("read_machine must not be called for an empty RunChoices")

    monkeypatch.setattr("voxtrama.diagnostics.machine.read_machine", _boom)

    assert check_resource_choice(RunChoices()) == []
