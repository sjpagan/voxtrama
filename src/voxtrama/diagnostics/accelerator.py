"""Which accelerator torch can use on this machine, if any.

`torch.cuda.is_available()` alone is not enough: it is `False`
on every Apple Silicon Mac even with Metal available, so a report built
only from it calls a machine "no GPU" when it has one. This asks torch,
already a dependency, for both APIs it exposes, and names
which one answered rather than collapsing them into a yes/no.
"""

from __future__ import annotations


def detect_accelerator() -> str | None:
    """Which accelerator torch can use here: "cuda", "mps", or None.

    Any failure (missing torch, a probe that raises) is "no
    accelerator": in 0.1 every profile runs on CPU regardless, so this
    is information for the reader, not a switch a caller acts on.
    """
    try:
        import torch
    except ImportError:
        return None
    try:
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    try:
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return None
