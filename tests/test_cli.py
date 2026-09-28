"""Tests for the Voxtrama CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from fakes.db import seed_local_user
from fakes.queue import InMemoryQueue
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

import voxtrama.cli.commands.run as run_command
from voxtrama.cli.main import app
from voxtrama.db.models import Base, Recording

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() != ""


def test_run_command_fails_on_missing_audio(tmp_path: Path) -> None:
    missing = tmp_path / "missing.wav"
    result = runner.invoke(app, ["run", "demo-workflow", str(missing)])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def _fake_import_local_file(session, source, paths, created_by=None):
    """Skip ffprobe: this suite is about which id the CLI prints, not ffprobe.

    Module-level, not a closure inside the test below: nesting it there
    put that test one line over the project's 40-line body limit the moment
    `created_by` was added to its signature. That limit asks for dividing
    by context, not compressing.
    """
    recording = Recording(
        original_filename=source.name,
        stored_path=f"recordings/fake/{source.name}",
        content_sha256="0" * 64,
        duration_seconds=1.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def test_run_command_prints_the_run_id_not_the_job_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake audio")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    seed_local_user(engine)
    monkeypatch.setattr(run_command, "build_session_factory", lambda: sessionmaker(bind=engine))
    monkeypatch.setattr(run_command, "import_local_file", _fake_import_local_file)

    submitted_run_ids: list[str] = []

    class _RecordingQueue(InMemoryQueue):
        def submit(self, run_id: str, job_timeout: int | None = None, job_id=None) -> str:
            submitted_run_ids.append(run_id)
            return super().submit(run_id, job_timeout=job_timeout, job_id=job_id)

    fake_queue = _RecordingQueue()
    monkeypatch.setattr(run_command, "_build_queue", lambda: fake_queue)

    # --detach: this checks what is printed, not the watching.
    result = runner.invoke(app, ["run", "transcribe-only", str(audio), "--detach"])

    assert result.exit_code == 0
    printed = result.output.strip().splitlines()[-1]
    assert submitted_run_ids == [printed]
