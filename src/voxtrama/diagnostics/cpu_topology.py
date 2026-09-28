"""What a single `os.cpu_count()` and a yes/no GPU flag miss on this machine.

Three facts, one probe: `sysctl` on Darwin, `/proc/cpuinfo` on Linux
where it applies. `os.cpu_count()` answers "how many", never "how many
of what": on an Apple Silicon Mac some cores are performance and some
are efficiency, and a chunk-parallelism advisor that counts them as
interchangeable proposes more parallel chunks than the machine can run
without swapping. Darwin exposes the split through
`hw.perflevel0.logicalcpu` (performance) and `hw.perflevel1.logicalcpu`
(efficiency), read with `subprocess`: a command invocation, not a new
dependency (the promise in `machine.py`'s docstring still holds).
Linux has no equivalent split exposed the same way, so this never
invents one there: callers get a single count instead, same as on a
homogeneous Intel Mac where `perflevel1` comes back empty.

The processor's marketing name and whether its GPU shares CPU memory
(true only on Apple Silicon) are the same kind of fact: read if the
platform exposes it, unknown otherwise, never guessed.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path


def _read_sysctl(key: str) -> str | None:
    """One `sysctl -n` value, or None if the command is missing, fails, or blank.

    A blank result is how Darwin answers `hw.perflevel1.logicalcpu` on a
    machine with no efficiency cores. It is treated the same as "unreadable"
    because the caller's fallback (a single count) is correct either way.
    """
    try:
        result = subprocess.run(
            ["sysctl", "-n", key], capture_output=True, text=True, timeout=2, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def read_core_topology() -> tuple[int | None, int | None]:
    """(performance cores, efficiency cores), or (None, None) where the split doesn't apply.

    Both come back None on Linux (no sysctl), on a homogeneous Mac
    (perflevel1 empty), and if sysctl fails outright. All three lead to
    the one answer a caller can act on: fall back to the single, unsplit
    cpu_count.
    """
    if platform.system() != "Darwin":
        return None, None
    performance = _read_sysctl("hw.perflevel0.logicalcpu")
    efficiency = _read_sysctl("hw.perflevel1.logicalcpu")
    if performance is None or efficiency is None:
        return None, None
    try:
        return int(performance), int(efficiency)
    except ValueError:
        return None, None


def has_unified_memory(architecture: str) -> bool:
    """Whether the GPU shares the CPU's memory pool instead of its own.

    True only on Apple Silicon (Darwin + arm64): its GPU has no
    discrete VRAM, so a "~N GB reserved per chunk" budget competes with
    everything else on the machine, not with a separate pool the way it
    does on a machine with a discrete GPU or none at all. The setup
    advisor is expected to act on this; here it is only declared.
    """
    return platform.system() == "Darwin" and architecture == "arm64"


def read_cpu_brand() -> str | None:
    """The processor's marketing name, where the platform exposes one.

    Darwin: `machdep.cpu.brand_string`, true on both Intel and Apple
    Silicon Macs. Linux: the first "model name" line of /proc/cpuinfo.
    Neither is guaranteed, so a miss is None rather than a guess.
    """
    if platform.system() == "Darwin":
        return _read_sysctl("machdep.cpu.brand_string")
    try:
        text = Path("/proc/cpuinfo").read_text()
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None
