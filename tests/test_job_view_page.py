"""The concluded job's view: head, tabs, the
Transcript tab's turns, the Recap tab and the address's ?tab= and ?merge=.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fakes.job_view import seed_concluded_job
from fakes.run_result import build_app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app, engine = build_app(tmp_path)
    seed_concluded_job(engine, tmp_path, "job-1")
    return TestClient(app)


def _turns(body: str) -> list[str]:
    return re.findall(r'<li class="vx-turn vx-turn--(\w+)" data-start="([\d.]+)"', body)


def test_a_concluded_job_opens_on_the_recap_under_its_own_head(client: TestClient) -> None:
    body = client.get("/runs/job-1/view").text

    assert 'id="vx-tab-recap" value="recap" checked' in body
    assert 'class="vx-job-settings"' in body and "Meeting decisions" in body
    assert "Regenerate job" in body
    assert 'class="vx-breadcrumb' not in body


def test_the_recap_names_the_source_and_the_provenance_of_each_point(client: TestClient) -> None:
    body = client.get("/runs/job-1/view").text

    assert "Key points" in body and "Decisions" in body
    assert body.index("Key points") < body.index("Decisions")
    assert 'data-start="8.0">spk1 · 0:08</button>' in body
    assert "meeting-decisions · extract_decisions · llama3.1:8b" in body
    assert 'href="/runs/job-1/recap.pdf"' in body and 'href="/runs/job-1/recap.docx"' in body


def test_turns_join_one_speakers_segments_until_a_pause(client: TestClient) -> None:
    body = client.get("/runs/job-1/view?tab=transcript").text

    assert 'id="vx-tab-transcript" value="transcript" checked' in body
    # Alex (0-8), Taylor (8-12), Alex (12-15), Alex again after 6 s.
    assert _turns(body) == [("left", "0.0"), ("right", "8.0"), ("left", "12.0"), ("left", "21.0")]
    assert "Thanks for making time today. Let" in body
    assert "Original segments" in body


def test_a_longer_merge_threshold_joins_across_the_pause(client: TestClient) -> None:
    body = client.get("/runs/job-1/view?tab=transcript&merge=8").text

    assert [start for _, start in _turns(body)] == ["0.0", "8.0", "12.0"]
    assert 'id="vx-merge" name="merge" min="0.5" max="5" step="0.1" value="8.0"' in body


def test_the_cards_state_their_evidence_or_its_absence(client: TestClient) -> None:
    body = client.get("/runs/job-1/view").text

    assert "Evidence: spk0 at 0:12-0:15" in body
    assert "No evidence" in body
    assert "Speaker names are assigned automatically" in body


def test_explore_filters_by_speaker_with_a_plain_text_field(client: TestClient) -> None:
    body = client.get("/runs/job-1/view").text

    assert '<option value="spk1">spk1</option>' in body
    assert 'type="search"' not in body.split('id="vx-run-transcript"')[1].split("</div>")[0]


def test_the_transcript_follows_the_audio(client: TestClient) -> None:
    """The line being spoken is marked as the player runs (static/js/job_follow.js)."""
    body = client.get("/runs/job-1/view").text

    assert "js/job_follow.js" in body
    assert body.index("js/run_result.js") < body.index("js/job_follow.js")


def test_every_speaker_chip_can_fix_its_sentence(client: TestClient) -> None:
    body = client.get("/runs/job-1/view").text

    assert body.count('action="/runs/job-1/segments/speaker"') >= 5
    assert "Who is speaking here?" in body


def test_fixing_one_sentence_moves_only_that_sentence(client: TestClient) -> None:
    body = client.get("/runs/job-1/view?tab=explore").text
    first = re.search(r'name="segment_id" value="([^"]+)"', body.split('id="vx-run-transcript"')[1])

    response = client.post(
        "/runs/job-1/segments/speaker",
        data={"segment_id": first.group(1), "new_name": "Sam", "tab": "explore"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/runs/job-1/view?tab=explore"
    after = client.get("/runs/job-1/view?tab=explore").text.split('id="vx-run-transcript"')[1]
    assert after.count(">Sam</summary>") == 1


def test_a_person_of_another_recording_is_refused(client: TestClient) -> None:
    response = client.post(
        "/runs/job-1/segments/speaker", data={"segment_id": "x", "person_id": "someone-else"}
    )

    assert response.status_code == 422


def test_regenerate_says_what_a_new_context_and_a_new_model_redo(client: TestClient) -> None:
    """A context redoes what follows the transcript. Another
    transcription model redoes the transcript, said once it is picked (CSS)."""
    panel = client.get("/runs/job-1/view").text.split('id="vx-regenerate"')[1]

    assert "not the transcript already made" in panel
    assert " data-current>Whisper" in panel and 'class="vx-regenerate__warn"' in panel
