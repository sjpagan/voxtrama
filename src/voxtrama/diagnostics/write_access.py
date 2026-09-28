"""Who writes the files, and whether each folder takes a write.

Settings › Data & privacy shows it, read-only: the account the operating
system reports, the owner of the data folder, the identity Voxtrama runs
as, and for every folder a real write (diagnostics.identity's probe, the
same one `voxtrama doctor` runs). When a write fails the page names the
cause and the fix. VOXTRAMA_RUN_AS_UID/GID stay environment variables:
the page shows them, it does not set them.

The fix is never "make it world-writable": that would let every user and
process on the machine read and change the recordings.
"""

from __future__ import annotations

import errno
import os
from dataclasses import dataclass
from pathlib import Path

from voxtrama.config.paths import get_paths
from voxtrama.diagnostics.identity import PROBE_NAME

MISSING = "missing"
READ_ONLY = "read_only"
OWNER = "owner"  # owned by someone other than the identity Voxtrama runs as
PERMISSIONS = "permissions"  # its owner is not allowed to write
OTHER = "other"


@dataclass(frozen=True)
class Account:
    uid: int | None
    gid: int | None
    name: str | None


@dataclass(frozen=True)
class FolderCheck:
    key: str  # data, recordings, runs, models
    path: str
    owner: Account
    ok: bool
    cause: str | None
    detail: str | None


@dataclass(frozen=True)
class WriteAccess:
    os_user: str | None
    runs_as: Account
    run_as_uid: str | None  # VOXTRAMA_RUN_AS_UID as set, None when not set
    run_as_gid: str | None
    folders: tuple[FolderCheck, ...]


def _name(uid: int | None) -> str | None:
    try:
        import pwd

        return pwd.getpwuid(uid).pw_name if uid is not None else None
    except (ImportError, KeyError):  # Windows, or a uid with no account here
        return None


def _account(uid: int | None, gid: int | None) -> Account:
    return Account(uid, gid, _name(uid))


def _owner(path: Path) -> Account:
    try:
        info = path.stat()
    except OSError:
        return Account(None, None, None)
    return _account(getattr(info, "st_uid", None), getattr(info, "st_gid", None))


def _cause(exc: OSError, owner: Account, runs_as: Account) -> str:
    if exc.errno == errno.EROFS:
        return READ_ONLY
    if exc.errno in (errno.EACCES, errno.EPERM):
        return OWNER if owner.uid is not None and owner.uid != runs_as.uid else PERMISSIONS
    return OTHER


def check_folder(key: str, path: Path, runs_as: Account) -> FolderCheck:
    """Write and remove a file in `path`; say why when it does not work."""
    if not path.is_dir():
        return FolderCheck(key, str(path), Account(None, None, None), False, MISSING, None)
    owner = _owner(path)
    probe = path / PROBE_NAME
    try:
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as exc:
        return FolderCheck(key, str(path), owner, False, _cause(exc, owner, runs_as), str(exc))
    return FolderCheck(key, str(path), owner, True, None, None)


def _runs_as() -> Account:
    try:
        return _account(os.getuid(), os.getgid())
    except AttributeError:  # Windows has neither
        return Account(None, None, None)


def write_access(data_dir: Path, models_dir: Path | None = None) -> WriteAccess:
    """Everything the card shows, read now; a folder not created yet is skipped."""
    runs_as = _runs_as()
    paths = get_paths(data_dir)
    folders = [check_folder("data", data_dir, runs_as)]
    for key, path in (
        ("recordings", paths.recordings_dir),
        ("runs", paths.runs_dir),
        ("models", models_dir or paths.models_dir),
    ):
        if path.is_dir():
            folders.append(check_folder(key, path, runs_as))
    return WriteAccess(
        os_user=os.environ.get("USER") or os.environ.get("LOGNAME") or runs_as.name,
        runs_as=runs_as,
        run_as_uid=os.environ.get("VOXTRAMA_RUN_AS_UID") or None,
        run_as_gid=os.environ.get("VOXTRAMA_RUN_AS_GID") or None,
        folders=tuple(folders),
    )
