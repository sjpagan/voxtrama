"""Stable JSON serialization and atomic writes, shared by everything under runs/<run_id>/.

Two files need the same two mechanics today (writer.py's manifest.json,
output.py's output.json), and a third is only a matter of time: rather than
each carrying its own copy, both call here.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def serialize(payload: Any) -> bytes:
    """Sorted keys, fixed separators: the file two runs are compared with.

    Not pretty-printing for its own sake: `diff` is how two manifests (or two
    outputs) get compared, and a diff against a dict-ordered dump produces
    noise on every run instead of only where they differ.
    """
    return json.dumps(payload, sort_keys=True, indent=2, separators=(",", ": ")).encode("utf-8")


def write_atomic(payload: Any, target: Path) -> bytes:
    """Serialize `payload` and replace `target` atomically. Returns the bytes written.

    Something may be reading this file while it is rewritten: a reader that
    catches a half-written file would see truncated JSON. mkstemp + os.replace
    is the same mechanism progress_file.py uses for the same reason.
    """
    data = serialize(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return data
