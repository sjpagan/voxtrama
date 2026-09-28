"""What this machine has, measured rather than assumed.

`voxtrama doctor` needs numbers before it can advise anything, and the
numbers have to come from somewhere that does not depend on a package we
would rather not add: memory, cores and free space are all readable from
the standard library on the platforms Voxtrama targets. `sysctl`, used by
diagnostics.cpu_topology for the parts Darwin only exposes that way, is a
system command invoked through `subprocess`, not a package either.

Every field is optional. A reading that cannot be taken is reported as
unknown instead of as a plausible zero: a diagnostic that invents a
number is worse than one that admits it does not have it.

`cpu_count` alone made every core look interchangeable, which is
wrong on Apple Silicon (performance and efficiency cores counted as one),
and `gpu_available` alone made every accelerator look the same, which is
wrong on a Mac (Metal reports as "no GPU" through the CUDA-only check this
used to run). Both are still here for whoever already reads them. The
finer fields sit next to them for the guided setup to use once it exists.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from voxtrama.diagnostics.accelerator import detect_accelerator
from voxtrama.diagnostics.cpu_topology import (
    has_unified_memory,
    read_core_topology,
    read_cpu_brand,
)


@dataclass(frozen=True)
class MachineReport:
    """The hardware and runtime facts `doctor` reports and reasons about."""

    platform: str
    architecture: str
    cpu_count: int | None
    performance_cores: int | None
    efficiency_cores: int | None
    cpu_brand: str | None
    total_memory_bytes: int | None
    unified_memory: bool
    free_disk_bytes: int | None
    gpu_available: bool
    accelerator: str | None
    in_container: bool


def read_total_memory_bytes() -> int | None:
    """Total physical memory, or None where it cannot be read.

    `sysconf` covers Linux and macOS, where Voxtrama runs today, and its
    container. Windows has neither key and returns None instead of a
    guess.
    """
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, ValueError, OSError):
        return None
    if pages < 0 or page_size < 0:
        return None
    return pages * page_size


def read_free_disk_bytes(path: Path) -> int | None:
    """Free space on the filesystem holding `path`, or None if unreadable.

    Asked of the data directory, not the root filesystem: what matters is
    where recordings, runs and several gigabytes of model weights will
    land.
    """
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def running_in_container() -> bool:
    """Whether this process runs inside a container.

    Changes what `doctor` can honestly say: inside the container the
    Docker version and the host's identity are not visible, and
    claiming otherwise would be a diagnostic that misleads.
    """
    if Path("/.dockerenv").exists():
        return True
    try:
        return "docker" in Path("/proc/1/cgroup").read_text()
    except OSError:
        return False


def read_machine(data_dir: Path) -> MachineReport:
    """Take every reading `doctor` reports, tolerating the ones that fail."""
    architecture = platform.machine()
    performance_cores, efficiency_cores = read_core_topology()
    accelerator = detect_accelerator()
    return MachineReport(
        platform=sys.platform,
        architecture=architecture,
        cpu_count=os.cpu_count(),
        performance_cores=performance_cores,
        efficiency_cores=efficiency_cores,
        cpu_brand=read_cpu_brand(),
        total_memory_bytes=read_total_memory_bytes(),
        unified_memory=has_unified_memory(architecture),
        free_disk_bytes=read_free_disk_bytes(data_dir),
        gpu_available=accelerator is not None,
        accelerator=accelerator,
        in_container=running_in_container(),
    )
