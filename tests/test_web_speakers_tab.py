"""The Speakers tab and the corrections a person makes to a job.

The request: a tab to name every speaker, count their turns and hear
them; speakers added by hand; one turn given to someone else only in
Explore; and a verified point that can be rewritten or tied to another
turn. The job here is fakes.job_view's: spk0 speaks four times, spk1 once.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fakes.job_view import seed_concluded_job
from fakes.run_result import build_app
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.db.models.transcript import Segment


@pytest.fixture
def job(tmp_path: Path):
    app, engine = build_app(tmp_path)
    seed_concluded_job(engine, tmp_path, "job-1")
    return TestClient(app, follow_redirects=False), engine, tmp_path


def _panel(body: str, tab: str) -> str:
    """The HTML of one tab's panel, up to the next one."""
    start = body.index(f'class="vx-tabs__panel" data-tab="{tab}"')
    following = body.find('class="vx-tabs__panel"', start + 1)
    return body[start : following if following > 0 else len(body)]


def test_the_tab_lists_each_voice_with_its_turns_and_a_minute_to_hear(job) -> None:
    client, _, _ = job

    panel = _panel(client.get("/runs/job-1/view").text, "speakers")

    assert 'name="speaker_name__spk0"' in panel and 'name="speaker_name__spk1"' in panel
    assert "4 turns" in panel and "1 turn " in panel
    clips = json.loads(re.search(r'data-clips="([^"]+)"', panel).group(1).replace("&#34;", '"'))
    assert clips[0] == [0.0, 4.0]


def test_a_name_follows_the_voice_everywhere(job) -> None:
    client, _, _ = job
    client.post(
        "/recordings/rec-job-1/speaker-names",
        data={"speaker_name__spk1": "Taylor Reed", "run_id": "job-1"},
    )

    body = client.get("/runs/job-1/view").text

    for tab in ("transcript", "explore"):  # the chips carry the given name
        assert ">Taylor<" in _panel(body, tab), tab
    assert 'value="Taylor Reed"' in _panel(body, "speakers")
    assert "1 turn " in _panel(body, "speakers")


def test_only_explore_fixes_a_single_turn(job) -> None:
    client, _, _ = job

    body = client.get("/runs/job-1/view").text

    assert "vx-speaker-fix" not in _panel(body, "transcript")
    assert "vx-speaker-fix" in _panel(body, "explore")
    assert "vx-speaker-naming-open" not in body  # the old dialog is gone


def test_an_added_speaker_can_be_given_one_turn_and_only_that_one(job) -> None:
    client, engine, _ = job
    response = client.post(
        "/recordings/rec-job-1/speakers", data={"name": "Jordan", "run_id": "job-1"}
    )
    assert response.headers["location"] == "/runs/job-1/view?tab=speakers"
    body = client.get("/runs/job-1/view").text
    assert 'name="speaker_name__+1"' in _panel(body, "speakers")
    person_id = re.search(r'<option value="([^"]+)"[^>]*>Jordan</option>', body).group(1)
    with Session(engine) as session:
        segments = session.scalars(select(Segment).order_by(Segment.start)).all()
        moved = segments[3].id

    client.post(
        "/runs/job-1/segments/speaker",
        data={"segment_id": moved, "person_id": person_id, "tab": "explore"},
    )

    speakers = _panel(client.get("/runs/job-1/view").text, "speakers")
    assert "3 turns" in speakers  # spk0 lost that one turn
    assert "1 turn " in speakers
    with Session(engine) as session:
        by_id = {s.id: s.person_id for s in session.scalars(select(Segment))}
    assert [pid for pid in by_id.values() if pid == person_id] == [person_id]


def test_a_point_rewritten_and_tied_to_a_turn_says_it_was_edited(job) -> None:
    client, _, tmp_path = job
    output = get_paths(tmp_path).runs_dir / "job-1" / "output.json"
    before = output.read_bytes()

    response = client.post(
        "/runs/job-1/output/edit",
        data={"ref": "summarize/key_points/0", "text": "Owners are needed.", "turn": "12.0:15.0"},
    )

    assert response.status_code == 303
    body = client.get("/runs/job-1/view").text
    assert "Owners are needed." in _panel(body, "transcript")
    assert "Owners are needed." in _panel(body, "recap")
    assert "Edited" in _panel(body, "recap")
    assert 'data-evidence-start="12.0"' in body
    assert output.read_bytes() == before  # what the model wrote stays


@pytest.mark.parametrize(
    "form",
    [
        {"ref": "summarize/key_points/9", "text": "x"},
        {"ref": "../../etc", "text": "x"},
        {"ref": "summarize/key_points/0", "text": "   "},
        {"ref": "summarize/key_points/0", "text": "x", "turn": "5:1"},
    ],
)
def test_a_correction_that_names_nothing_real_is_refused(job, form) -> None:
    client, _, _ = job

    assert client.post("/runs/job-1/output/edit", data=form).status_code == 422
