"""Tests for voxtrama.ingest.local_file.import_local_file."""

from __future__ import annotations

import hashlib
import wave
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.db.models import Recording
from voxtrama.db.people import local_user
from voxtrama.ingest import UnsupportedMediaError, import_local_file


def _write_wav(path: Path, seconds: float = 0.5, frame_rate: int = 8000) -> None:
    """Write a small, real PCM WAV file: silence, but audio ffprobe can read."""
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(frame_rate)
        handle.writeframes(b"\x00\x00" * int(frame_rate * seconds))


def test_import_local_file_creates_a_recording(tmp_path: Path, db_session: Session) -> None:
    source = tmp_path / "source" / "clip.wav"
    source.parent.mkdir()
    _write_wav(source, seconds=1.0)
    paths = get_paths(tmp_path / "data")

    recording = import_local_file(db_session, source, paths)

    assert recording.original_filename == "clip.wav"
    assert recording.media_format
    assert recording.duration_seconds == pytest.approx(1.0, abs=0.1)
    assert recording.content_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()


def test_import_local_file_copies_content_and_uses_the_original_filename(
    tmp_path: Path, db_session: Session
) -> None:
    source = tmp_path / "source" / "clip.wav"
    source.parent.mkdir()
    _write_wav(source)
    paths = get_paths(tmp_path / "data")

    recording = import_local_file(db_session, source, paths)

    stored = paths.data_dir / recording.stored_path
    assert stored.name == "clip.wav"
    assert stored.parent == paths.recordings_dir / recording.id
    assert stored.read_bytes() == source.read_bytes()


def test_import_local_file_persists_the_recording(tmp_path: Path, db_session: Session) -> None:
    source = tmp_path / "clip.wav"
    _write_wav(source)
    paths = get_paths(tmp_path / "data")

    recording = import_local_file(db_session, source, paths)

    assert db_session.get(Recording, recording.id) is not None


def test_import_local_file_two_imports_of_the_same_file_create_two_recordings(
    tmp_path: Path, db_session: Session
) -> None:
    source = tmp_path / "clip.wav"
    _write_wav(source)
    paths = get_paths(tmp_path / "data")

    first = import_local_file(db_session, source, paths)
    second = import_local_file(db_session, source, paths)

    assert first.id != second.id
    assert first.content_sha256 == second.content_sha256


def test_import_local_file_records_who_imported_it(tmp_path: Path, db_session: Session) -> None:
    """The local import also records who imported it: import_local_file writes
    the caller's created_by onto the Recording, called the same way the
    CLI calls it: cli.commands.run._import_and_enqueue resolves
    local_user() first and passes its id.
    """
    source = tmp_path / "clip.wav"
    _write_wav(source)
    paths = get_paths(tmp_path / "data")
    created_by = local_user(db_session).id

    recording = import_local_file(db_session, source, paths, created_by=created_by)

    assert recording.created_by == created_by


def test_import_local_file_rejects_a_non_audio_file(tmp_path: Path, db_session: Session) -> None:
    source = tmp_path / "notes.wav"
    source.write_text("this is a text file, not audio")
    paths = get_paths(tmp_path / "data")

    with pytest.raises(UnsupportedMediaError):
        import_local_file(db_session, source, paths)

    assert not paths.recordings_dir.exists()
