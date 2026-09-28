"""The Files tab's downloads: the transcript as a file, and the job's ZIP."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fakes.job_view import seed_concluded_job
from fakes.run_result import build_app
from fastapi.testclient import TestClient

from voxtrama.rendering.run_transcript import TranscriptRowView
from voxtrama.rendering.transcript_files import as_jsonl, as_text, parts_of


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app, engine = build_app(tmp_path)
    seed_concluded_job(engine, tmp_path, "job-1")
    return TestClient(app)


def _row(start: float, text: str = "t", speaker: str | None = "Anna") -> TranscriptRowView:
    return TranscriptRowView(str(start), start, start + 1, "0:00", speaker, 0, text)


def test_parts_close_on_a_sentence_past_each_ten_minutes() -> None:
    rows = [_row(0), _row(590), _row(605), _row(1300), _row(1900)]

    parts = parts_of(rows)

    assert [[r.start for r in p.rows] for p in parts] == [[0, 590], [605], [1300], [1900]]
    assert (parts[0].audio_start, parts[0].audio_end) == (0.0, 605)
    assert (parts[-1].audio_start, parts[-1].audio_end) == (1900, None)
    assert parts[1].stem == "part-02-10m05s"


def test_text_and_jsonl_carry_time_speaker_and_words() -> None:
    rows = [_row(0, "ciao"), _row(3, "noise", None)]

    assert as_text(rows) == "[0:00] Anna: ciao\n[0:00] noise\n"
    assert json.loads(as_jsonl(rows).splitlines()[1]) == {
        "start": 3,
        "end": 4,
        "speaker": None,
        "text": "noise",
    }


@pytest.mark.parametrize("fmt", ["txt", "md", "json", "jsonl"])
def test_the_transcript_downloads_in_each_format(client: TestClient, fmt: str) -> None:
    response = client.get(f"/runs/job-1/transcript.{fmt}")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "roadmap" in response.text


def test_an_unknown_format_or_job_is_404(client: TestClient) -> None:
    assert client.get("/runs/job-1/transcript.doc").status_code == 404
    assert client.get("/runs/nope/transcript.txt").status_code == 404


def test_the_package_holds_manifest_transcript_and_parts(client: TestClient) -> None:
    response = client.get("/runs/job-1/package.zip")

    names = set(zipfile.ZipFile(io.BytesIO(response.content)).namelist())
    assert {"README.txt", "transcript.txt", "transcript.jsonl", "parts/part-01-0m00s.txt"} <= names
    readme = zipfile.ZipFile(io.BytesIO(response.content)).read("README.txt").decode()
    assert "only their text" in readme  # the seeded recording has no file


def test_the_files_tab_lists_the_downloads(client: TestClient) -> None:
    page = client.get("/runs/job-1/view?tab=files").text

    assert 'href="/runs/job-1/package.zip"' in page
    assert 'href="/runs/job-1/transcript.jsonl"' in page
