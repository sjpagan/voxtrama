"""Tests for POST /recordings/{id}/speaker-names, and the "Name speakers"
button/panel it feeds.

Reuses fakes.run_result's own app-building helpers (the result page's own
fixture shape) with a Recording/Transcript pair this file seeds itself, since
insert_recording_and_transcript's own one Segment carries no speaker_label
at all, and that is what this file tests.
"""

from __future__ import annotations

from pathlib import Path

from fakes.run_result import build_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import Run, RunState
from voxtrama.db.models.transcript import Segment, Transcript


def _seed_two_speaker_run(engine: Engine, run_id: str) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_name="transcribe-only",
                workflow_version="1.0.0",
                state=RunState.SUCCEEDED,
                recording_id=f"rec-{run_id}",
            )
        )
        session.add(
            Recording(
                id=f"rec-{run_id}",
                original_filename="clip.wav",
                stored_path="x",
                content_sha256="a" * 64,
                duration_seconds=10.0,
                media_format="wav",
            )
        )
        transcript = Transcript(
            id=f"t-{run_id}",
            recording_id=f"rec-{run_id}",
            language="en",
            model_name="whisper",
            model_revision="v1",
            hardware_profile="cpu",
            produced_by_run_id=run_id,
        )
        transcript.segments = [
            Segment(start=0.0, end=2.0, text="hi", confidence=1.0, speaker_label="spk0"),
            Segment(start=2.0, end=3.0, text="hey", confidence=1.0, speaker_label="spk1"),
        ]
        session.add(transcript)
        session.commit()


def test_a_run_with_labelled_speakers_shows_the_speakers_tab(tmp_path: Path) -> None:
    app, engine = build_app(tmp_path)
    _seed_two_speaker_run(engine, "run-1")
    client = TestClient(app)

    body = client.get("/runs/run-1/view").text

    assert 'id="vx-tab-speakers"' in body  # The tab, not a dialog
    assert 'id="vx-speaker-naming"' not in body
    assert 'name="speaker_name__spk0"' in body
    assert 'name="speaker_name__spk1"' in body


def test_saving_a_name_redirects_to_the_run_page(tmp_path: Path) -> None:
    app, engine = build_app(tmp_path)
    _seed_two_speaker_run(engine, "run-2")
    client = TestClient(app)

    response = client.post(
        "/recordings/rec-run-2/speaker-names",
        data={"speaker_name__spk0": "Sarah Connor", "run_id": "run-2"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/runs/run-2/view?tab=speakers"


def test_the_new_name_replaces_the_raw_label_on_the_run_page(tmp_path: Path) -> None:
    app, engine = build_app(tmp_path)
    _seed_two_speaker_run(engine, "run-3")
    client = TestClient(app)

    client.post(
        "/recordings/rec-run-3/speaker-names",
        data={"speaker_name__spk0": "Sarah Connor", "run_id": "run-3"},
    )
    body = client.get("/runs/run-3/view").text

    assert "Sarah Connor" in body
    assert "spk1" in body  # left unnamed, still the raw label


def test_a_blank_field_names_nothing(tmp_path: Path) -> None:
    app, engine = build_app(tmp_path)
    _seed_two_speaker_run(engine, "run-4")
    client = TestClient(app)

    client.post("/recordings/rec-run-4/speaker-names", data={"run_id": "run-4"})
    body = client.get("/runs/run-4/view").text

    assert "spk0" in body
    assert "spk1" in body


def test_an_unknown_recording_is_404(tmp_path: Path) -> None:
    app, _engine = build_app(tmp_path)
    client = TestClient(app)

    response = client.post("/recordings/does-not-exist/speaker-names", data={"run_id": "x"})

    assert response.status_code == 404
