"""The manifest may show the host a model ran on, never the credential.

The same control tests/test_providers_secrets.py runs on log messages, one
layer up: OllamaProvider.host is already the stripped host (that module's
own test), so this proves the whole path to disk (RunStep, ManifestStep,
the written JSON) never reintroduces the credential some other way.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.manifest.writer import manifest_path, write_run_manifest
from voxtrama.workflow.definition import Step, Workflow

OLLAMA_URL = "http://127.0.0.1:11434"
SECRET = "super-secret-token"


def _workflow() -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[Step(id="summarize", skill="summarize", skill_version="1.0.0")],
    )


def _transcript() -> Transcript:
    transcript = Transcript(
        id="t1",
        recording_id="r1",
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="low",
    )
    transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1.0)]
    return transcript


def test_no_credential_anywhere_in_the_written_manifest(
    db_session: Session, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", OLLAMA_URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    monkeypatch.setenv("VOXTRAMA_OLLAMA_AUTH", SECRET)
    transport = install(monkeypatch)
    body = {"key_points": [{"text": "a greeting", "quote": "hello there"}]}
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
    run = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0")
    _, rows, context, _ = prepare_run(db_session, run, _workflow())
    context.transcript = _transcript()
    execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)

    write_run_manifest(tmp_path, run, rows, _workflow(), BUILTIN_SKILLS, None, context.transcript)
    text = manifest_path(tmp_path, run.id).read_text()

    assert SECRET not in text
    assert "127.0.0.1:11434" in text
