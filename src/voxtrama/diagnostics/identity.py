"""Who this process is, who owns the data directory, and whether it can write.

Ownership is aligned at container start, and `doctor` has to
show the result with a real write, not with arithmetic on uid numbers.
Three identities can disagree (the user at the terminal, the owner of the
folder, the process inside the container), and the only question that
matters is whether a file lands. So we create one and delete it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROBE_NAME = ".voxtrama-write-probe"


@dataclass(frozen=True)
class IdentityReport:
    """The three identities involved in writing, and the proof that it works."""

    process_uid: int | None
    process_gid: int | None
    data_dir_uid: int | None
    data_dir_gid: int | None
    data_dir_exists: bool
    write_ok: bool
    write_error: str | None


def _process_ids() -> tuple[int | None, int | None]:
    try:
        return os.getuid(), os.getgid()
    except AttributeError:  # Windows has neither
        return None, None


def _owner_ids(path: Path) -> tuple[int | None, int | None]:
    try:
        info = path.stat()
    except OSError:
        return None, None
    return getattr(info, "st_uid", None), getattr(info, "st_gid", None)


def probe_write(directory: Path) -> tuple[bool, str | None]:
    """Create and delete a file in `directory`; report what went wrong if it did.

    Permissions on a bind mount, on a network share or under a remapped
    uid can look right and still refuse a write, and a user reading a
    diagnostic deserves the answer instead of the ingredients of one.
    """
    probe = directory / PROBE_NAME
    try:
        probe.write_bytes(b"")
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    try:
        probe.unlink()
    except OSError as exc:
        return False, f"written but not removable ({type(exc).__name__}: {exc})"
    return True, None


def read_identity(data_dir: Path) -> IdentityReport:
    """Collect both identities and run the write probe against `data_dir`."""
    process_uid, process_gid = _process_ids()
    exists = data_dir.is_dir()
    owner_uid, owner_gid = _owner_ids(data_dir) if exists else (None, None)
    if exists:
        write_ok, write_error = probe_write(data_dir)
    else:
        write_ok, write_error = False, "the data directory does not exist"
    return IdentityReport(
        process_uid=process_uid,
        process_gid=process_gid,
        data_dir_uid=owner_uid,
        data_dir_gid=owner_gid,
        data_dir_exists=exists,
        write_ok=write_ok,
        write_error=write_error,
    )
