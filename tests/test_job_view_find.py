"""The one search of the job view, and the player's jumps."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fakes.job_view import seed_concluded_job
from fakes.run_result import build_app
from fastapi.testclient import TestClient

STATIC_JS = Path(__file__).resolve().parents[1] / "src" / "voxtrama" / "web" / "static" / "js"


@pytest.fixture
def body(tmp_path: Path) -> str:
    app, engine = build_app(tmp_path)
    seed_concluded_job(engine, tmp_path, "job-1")
    return TestClient(app).get("/runs/job-1/view").text


def test_the_same_search_is_in_transcript_explore_and_recap(body: str) -> None:
    scopes = re.findall(
        r'class="vx-find" data-find-scope="([^"]+)" data-find-texts="([^"]+)"', body
    )

    assert scopes == [
        ("#vx-turns", ".vx-turn__text"),
        ("#vx-transcript-rows", ".vx-transcript__text"),
        ("#vx-recap-body", ".vx-recap__text"),
    ]
    assert body.count('class="vx-find__count" data-of="of"') == 3
    assert body.count('class="vx-find__step" data-step="1"') == 3


def test_the_search_runs_in_the_page_not_on_the_server(body: str) -> None:
    script = (STATIC_JS / "text_find.js").read_text()

    assert "text_find.js" in body
    assert "fetch(" not in script and "XMLHttpRequest" not in script
    assert "currentTime" in script  # the player follows the match


def test_the_player_jumps_back_and_forward(body: str) -> None:
    skips = re.findall(r'class="vx-player__skip" data-skip="(-?\d+)"[^>]*>([^<]+)<', body)

    assert skips == [("-60", "«60s"), ("-10", "«10s"), ("10", "10s»"), ("60", "60s»")]
