"""What `doctor` measures, and the advice it derives from it."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from voxtrama.diagnostics import advise_profile, read_identity, read_machine, warnings
from voxtrama.diagnostics.advice import COMFORTABLE_FREE_DISK_BYTES, GIB
from voxtrama.diagnostics.identity import PROBE_NAME


def test_reading_a_machine_reports_what_it_can(tmp_path: Path) -> None:
    machine = read_machine(tmp_path)

    assert machine.platform
    assert machine.free_disk_bytes is not None and machine.free_disk_bytes > 0


def test_the_write_probe_leaves_nothing_behind(tmp_path: Path) -> None:
    identity = read_identity(tmp_path)

    assert identity.write_ok
    assert identity.write_error is None
    assert not (tmp_path / PROBE_NAME).exists()


def test_a_missing_data_directory_is_not_writable(tmp_path: Path) -> None:
    identity = read_identity(tmp_path / "nowhere")

    assert not identity.data_dir_exists
    assert not identity.write_ok
    assert identity.write_error is not None


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores the permission bits this asserts on",
)
def test_a_read_only_directory_fails_the_probe_rather_than_being_deduced(tmp_path: Path) -> None:
    """The probe is the point: permissions that look fine can still refuse."""
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        identity = read_identity(locked)
    finally:
        locked.chmod(0o700)

    assert not identity.write_ok
    assert identity.write_error is not None


def test_the_profile_follows_the_memory_thresholds_of_adr_0009(tmp_path: Path) -> None:
    machine = read_machine(tmp_path)

    assert advise_profile(replace(machine, total_memory_bytes=8 * GIB))[0] == "low"
    assert advise_profile(replace(machine, total_memory_bytes=16 * GIB))[0] == "base"
    assert advise_profile(replace(machine, total_memory_bytes=64 * GIB))[0] == "high"


def test_no_memory_reading_means_no_suggestion(tmp_path: Path) -> None:
    """Better the user chose than have us guess for them."""
    machine = replace(read_machine(tmp_path), total_memory_bytes=None)

    suggested, reason = advise_profile(machine)

    assert suggested is None
    assert "no profile is suggested" in reason


def test_a_full_disk_is_warned_about(tmp_path: Path) -> None:
    machine = replace(read_machine(tmp_path), free_disk_bytes=COMFORTABLE_FREE_DISK_BYTES - 1)

    assert any("free where the data directory lives" in line for line in warnings(machine))


def test_a_healthy_machine_can_have_nothing_to_warn_about(tmp_path: Path) -> None:
    """A diagnostic that always complains is as useless as one that never does."""
    machine = replace(
        read_machine(tmp_path),
        free_disk_bytes=500 * GIB,
        cpu_count=8,
        gpu_available=False,
    )

    assert warnings(machine) == []
