"""The five prescribed fields reach the row and the manifest, end to end.

Runs a real three-step workflow (transcribe, diarize, summarize) through
engine.run.execute_run, the way a worker does. faster-whisper and
diarization.assign_speakers are both faked (heavy, network-touching
libraries a network-free test must not load). Ollama is faked like every
other engine test here, through tests/fakes/http_transport.py. The
manifest carries, per step, where its model ran, no step muted.
transcribe in isolation is in test_engine_step_transcribe_provenance.py.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.recording import Recording
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.workflow.definition import Step, Workflow

OLLAMA_URL = "http://127.0.0.1:11434"


def _fake_transcribe(recording, hardware_profile, on_download=None, on_progress=None, **_ignored):
    """Stands in for transcription.asr.transcribe: no faster-whisper, no audio file."""
    transcript = Transcript(
        recording_id=recording.id,
        language="en",
        model_name="whisper-fake",
        model_revision="rev-9",
        hardware_profile=hardware_profile,
    )
    transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1.0)]
    return transcript


def _fake_assign_speakers(
    transcript, audio_path, models_dir, max_speakers=4, on_download=None, on_progress=None
):
    """Stands in for diarization.assign_speakers: no speechbrain, no ECAPA weights."""
    transcript.speaker_estimate = 1
    transcript.speaker_cap = max_speakers
    return transcript


def _recording(session: Session) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="0" * 64,
        duration_seconds=2.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", OLLAMA_URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    monkeypatch.setattr("voxtrama.transcription.transcribe", _fake_transcribe)
    monkeypatch.setattr("voxtrama.diarization.assign_speakers", _fake_assign_speakers)


def _route_ollama(monkeypatch: pytest.MonkeyPatch, body: dict) -> None:
    transport = install(monkeypatch)
    transport.route(
        f"{OLLAMA_URL}/api/generate",
        FakeResponse(200, json.dumps({"response": json.dumps(body)}).encode()),
    )
    transport.route(
        f"{OLLAMA_URL}/api/tags",
        FakeResponse(
            200, json.dumps({"models": [{"name": "qwen-test", "digest": "sha256:x"}]}).encode()
        ),
    )


def _three_step_workflow() -> Workflow:
    return Workflow(
        name="transcribe-diarize-summarize",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[
            Step(id="transcribe", skill="transcribe", skill_version="1.0.0"),
            Step(id="diarize", skill="diarize", skill_version="1.0.0", depends_on=["transcribe"]),
            Step(
                id="summarize",
                skill="summarize",
                skill_version="1.0.0",
                depends_on=["diarize"],
            ),
        ],
    )


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def test_a_three_step_run_reports_the_five_prescribed_fields_for_each_step(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    _route_ollama(monkeypatch, {"key_points": [{"text": "a greeting", "quote": "hello there"}]})
    recording = _recording(db_session)
    workflow = _three_step_workflow()
    created = create_run(db_session, workflow.name, "unpinned", recording_id=recording.id)

    run = execute_run(db_session, created.id, workflow=workflow)

    manifest = _read_manifest(run.id)
    assert manifest.run.state == "succeeded"
    by_id = {step.step_id: step for step in manifest.steps}
    for step_id in ("transcribe", "diarize", "summarize"):
        print(json.dumps(by_id[step_id].model_dump(mode="json"), indent=2, sort_keys=True))

    assert (by_id["transcribe"].model, by_id["transcribe"].model_revision) == (
        "whisper-fake",
        "rev-9",
    )
    # "local"/None/False, not a mute None: see run_transcribe's own docstring.
    assert (by_id["transcribe"].provider, by_id["transcribe"].host) == ("local", None)
    assert by_id["transcribe"].profile_check_skipped is False

    # diarize is not muted either (the defect this test guards against):
    # its revision is pinned for security.
    assert by_id["diarize"].model == "speechbrain/spkrec-ecapa-voxceleb"
    assert by_id["diarize"].model_revision == "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"
    assert (by_id["diarize"].provider, by_id["diarize"].host) == ("local", None)
    assert by_id["diarize"].profile_check_skipped is False

    assert by_id["summarize"].model == "qwen-test"
    assert by_id["summarize"].model_revision == "sha256:x"
    assert by_id["summarize"].provider == "ollama"
    assert by_id["summarize"].host == "127.0.0.1:11434"
    assert by_id["summarize"].profile_check_skipped is False
