"""Whether the data directory is usable.

Reuses diagnostics.identity's real write probe and diagnostics.machine's
free-space reading instead of repeating either: permissions on a bind
mount, a network share or a remapped uid can look right and still refuse a
write, and only creating a file and removing it tells the truth. Free
space reuses the advice.COMFORTABLE_FREE_DISK_BYTES threshold, so
"enough space" means the same 10 GiB here as it does in `doctor`'s
warnings.
"""

from __future__ import annotations

from voxtrama.config.settings import Settings
from voxtrama.diagnostics.advice import COMFORTABLE_FREE_DISK_BYTES, GIB
from voxtrama.diagnostics.identity import read_identity
from voxtrama.diagnostics.machine import read_free_disk_bytes
from voxtrama.diagnostics.readiness_state import PrivateStorageCheck, Readiness


def check_private_storage(settings: Settings) -> PrivateStorageCheck:
    """Check that the data directory exists, accepts a real write, and has room to spare."""
    identity = read_identity(settings.data_dir)
    free = read_free_disk_bytes(settings.data_dir)
    if not identity.data_dir_exists:
        return PrivateStorageCheck(
            state=Readiness.NOT_READY,
            reason=f"the data directory {settings.data_dir} does not exist",
            free_disk_bytes=free,
        )
    if not identity.write_ok:
        return PrivateStorageCheck(
            state=Readiness.NOT_READY,
            reason=f"the data directory is not writable: {identity.write_error}",
            free_disk_bytes=free,
        )
    if free is None:
        return PrivateStorageCheck(
            state=Readiness.UNKNOWN,
            reason="free disk space could not be read",
            free_disk_bytes=None,
        )
    if free < COMFORTABLE_FREE_DISK_BYTES:
        return PrivateStorageCheck(
            state=Readiness.NOT_READY,
            reason=f"only {free / GIB:.1f} GiB free, not enough for model weights and recordings",
            free_disk_bytes=free,
        )
    return PrivateStorageCheck(
        state=Readiness.READY, reason=f"{free / GIB:.1f} GiB free", free_disk_bytes=free
    )
