"""A machine with a known core count, for tests whose numbers a real host would cap.

transcription.resources and engine.resource_choice cap cores at what the
machine has; a test asking for 3 or 7 cores on a 2-core runner would
otherwise read back 2 and fail for a reason that is not the code's.
"""

from __future__ import annotations

import pytest

from voxtrama.diagnostics.machine import MachineReport


def eight_cores(data_dir: object = None) -> MachineReport:
    return MachineReport(
        platform="test",
        architecture="x86_64",
        cpu_count=8,
        performance_cores=None,
        efficiency_cores=None,
        cpu_brand=None,
        total_memory_bytes=16 * 1024**3,
        unified_memory=False,
        free_disk_bytes=100 * 1024**3,
        gpu_available=False,
        accelerator=None,
        in_container=False,
    )


def use_eight_cores(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patched where it is defined: callers resolve it through the module at call time."""
    monkeypatch.setattr("voxtrama.diagnostics.machine.read_machine", eight_cores)
