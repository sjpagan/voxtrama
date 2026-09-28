"""Imports a local audio file into the data directory as a Recording.

No HTTP, no CLI: this is the core operation both entrypoints call.
Callers pass a `Paths`, never a bare data directory string, so the layout
stays the single source of truth `config.paths` already is.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from voxtrama.config.paths import Paths
from voxtrama.db.models.recording import Recording
from voxtrama.ingest.probe import probe_media
from voxtrama.ingest.recording_row import persist_new_recording
from voxtrama.ingest.resample import needs_resample, resample_to_16k_mono, resampled_sibling

# 1 MiB: large enough to amortise the read/write syscalls over a long
# recording, small enough that importing one never loads it whole into memory.
_COPY_CHUNK_SIZE = 1024 * 1024


def _copy_with_hash(source: Path, destination: Path) -> str:
    """Copy `source` to `destination` in chunks, hashing as it writes.

    An hour-long recording is read once, not read again afterwards just to
    compute a hash that could have come from the same pass.
    """
    digest = hashlib.sha256()
    with source.open("rb") as src, destination.open("wb") as dst:
        while chunk := src.read(_COPY_CHUNK_SIZE):
            dst.write(chunk)
            digest.update(chunk)
    return digest.hexdigest()


def _copy_and_prepare(
    source: Path,
    destination: Path,
    destination_dir: Path,
    media_format: str,
    sample_rate: int,
    channels: int,
) -> str:
    """Copy `source` into `destination`, then resample it if a run needs that.

    Cleans up its own partial output on failure (the copy, any resampled
    sibling, and the now-empty directory), so import_local_file's caller
    sees a clean failure, never a Recording pointing at a truncated file.
    """
    try:
        content_sha256 = _copy_with_hash(source, destination)
        if needs_resample(media_format, sample_rate, channels):
            resample_to_16k_mono(destination, resampled_sibling(destination))
        return content_sha256
    except Exception:
        resampled_sibling(destination).unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        destination_dir.rmdir()
        raise


# Names Voxtrama writes beside a recording: its 16 kHz copy, the cleaned
# copy, the waveform cache. An upload named `peaks-v3.json` was once
# overwritten by the waveform and lost.
_GENERATED_PREFIXES = ("resampled_", "cleaned_", "peaks-")


def stored_name(name: str) -> str:
    """The file name a recording is kept under: its own, unless Voxtrama uses it."""
    return f"original-{name}" if name.startswith(_GENERATED_PREFIXES) else name


def import_local_file(
    session: Session,
    source: Path,
    paths: Paths,
    created_by: str | None = None,
    source_title: str | None = None,
    source_url: str | None = None,
) -> Recording:
    """Import `source` into the data directory and persist it as a Recording.

    The Recording row is written only once the copy is complete and the
    hash is known: a row pointing at a truncated file is worse than no row
    at all, since the run it starts would fail later with no clue why.

    `created_by` is a user id the caller already resolved, not looked up
    here: ingest is core and cannot call db.people.local_user. It defaults
    to None, and stays None if the caller does not pass it: a Recording
    without a known importer is a valid row, not an error.

    `source_title` and `source_url` were the URL import's to give, since
    removed. Both default to `None` and nothing passes them any more.
    """
    duration_seconds, media_format, sample_rate, channels = probe_media(source)

    recording_id = str(uuid.uuid4())
    destination_dir = paths.recordings_dir / recording_id
    destination = destination_dir / stored_name(source.name)
    destination_dir.mkdir(parents=True, exist_ok=True)

    content_sha256 = _copy_and_prepare(
        source, destination, destination_dir, media_format, sample_rate, channels
    )

    return persist_new_recording(
        session,
        recording_id,
        source.name,
        str(destination.relative_to(paths.data_dir)),
        (content_sha256, duration_seconds, media_format),
        created_by,
        source_title,
        source_url,
    )
