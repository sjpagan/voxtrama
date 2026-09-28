"""GET /runs/{id}/package.zip: everything a concluded job produced, in one file.

The job's files to take away: one ZIP with the manifest to share (api.routes.
run_manifest_export, without the context's text or any host), the full
transcript as text, Markdown and JSON, and the recording in parts of
about ten minutes, each part's MP3 next to its part of the transcript, so
a long call can be worked on a piece at a time. A job whose recording is
gone, or a machine where ffmpeg cannot cut it, still gets the text parts;
the README inside says which.

Built in a temporary folder and removed once sent: nothing is added to
the data folder.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from voxtrama.api.deps import DbDep, SettingsDep
from voxtrama.api.routes.job_files import render, transcript_rows
from voxtrama.api.routes.run_lookup import get_run_or_404
from voxtrama.api.routes.run_manifest_export import file_stem, shared_manifest
from voxtrama.config.paths import get_paths
from voxtrama.db.models.recording import Recording
from voxtrama.humanize import human_clock
from voxtrama.ingest.audio_cut import cut_mp3
from voxtrama.rendering.transcript_files import Part, as_text, parts_of

router = APIRouter()


def _readme(title: str, parts: list[Part], with_audio: bool) -> str:
    lines = [
        f"{title}\n",
        "manifest.json      what the job ran with (context text and hosts removed)",
        "transcript.txt     the whole transcript, one sentence per line",
        "transcript.md      the same, as Markdown",
        "transcript.json    the same, with start and end in seconds",
        "transcript.jsonl   one sentence per line as JSON, for scripts and search indexes",
        "parts/             the job in parts of about ten minutes:",
    ]
    for part in parts:
        end = human_clock(part.audio_end) if part.audio_end is not None else "end"
        lines.append(f"  {part.stem}  {human_clock(part.audio_start)} to {end}")
    if not with_audio:
        lines.append("\nThe recording was not available: the parts hold only their text.")
    return "\n".join(lines) + "\n"


def _audio(session, settings, recording_id: str | None) -> Path | None:
    recording = session.get(Recording, recording_id) if recording_id else None
    if recording is None:
        return None
    path = get_paths(settings.data_dir).data_dir / recording.stored_path
    return path if path.exists() else None


def _write_parts(
    archive: zipfile.ZipFile, parts: list[Part], audio: Path | None, work: Path
) -> bool:
    """Each part's text, and its MP3 while ffmpeg manages; whether every MP3 was written."""
    audio_ok = audio is not None
    for part in parts:
        archive.writestr(f"parts/{part.stem}.txt", as_text(part.rows))
        if not audio_ok:
            continue
        target = work / f"{part.stem}.mp3"
        try:
            cut_mp3(audio, target, part.audio_start, part.audio_end)
        except (OSError, subprocess.CalledProcessError):
            audio_ok = False
            continue
        archive.write(target, f"parts/{part.stem}.mp3", compress_type=zipfile.ZIP_STORED)
        target.unlink()
    return audio_ok


@router.get("/runs/{run_id}/package.zip")
def job_package_route(run_id: str, session: DbDep, settings: SettingsDep) -> FileResponse:
    """The job's files as one ZIP download."""
    run = get_run_or_404(run_id, session)
    rows = transcript_rows(session, settings, run)
    title = run.label or run.workflow_name
    parts = parts_of(rows)
    work = Path(tempfile.mkdtemp(prefix="vx-package-"))
    zip_path = work / "package.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        manifest = shared_manifest(get_paths(settings.data_dir).runs_dir, run.id)
        if manifest is not None:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        for fmt in ("txt", "md", "json", "jsonl"):
            archive.writestr(f"transcript.{fmt}", render(fmt, title, rows))
        audio_ok = _write_parts(archive, parts, _audio(session, settings, run.recording_id), work)
        archive.writestr("README.txt", _readme(title, parts, audio_ok))
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{file_stem(run)}.zip",
        background=BackgroundTask(shutil.rmtree, work, ignore_errors=True),
    )
