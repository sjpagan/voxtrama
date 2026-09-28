"""A custom step's own instructions are what the model receives."""

from __future__ import annotations

import json

from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.workflow.definition import Step, Workflow

URL = "http://127.0.0.1:11434"
MINE = "Only the three most important points, as JSON key_points.\n{transcript}"


def test_the_step_sends_its_own_instructions_and_the_skill_file_stays(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    get_settings.cache_clear()
    transport = install(monkeypatch)
    answer = json.dumps({"response": json.dumps({"key_points": []})}).encode()
    transport.route(f"{URL}/api/generate", FakeResponse(200, answer))
    transport.route(f"{URL}/api/tags", FakeResponse(200, json.dumps({"models": []}).encode()))
    step = Step(id="summarize", skill="summarize", skill_version="1.0.0", instructions=MINE)
    workflow = Workflow(name="w", version="1", schema_version="v1", description="d", steps=[step])
    _, rows, context, _ = prepare_run(db_session, create_run(db_session, "w", "unpinned"), workflow)
    context.transcript = Transcript(
        id="t1", recording_id="r1", language="en", model_name="w", model_revision="v1"
    )
    context.transcript.segments = [Segment(start=0.0, end=2.0, text="hello there", confidence=1)]

    execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)

    sent = [c for c in transport.calls if c.full_url.endswith("/api/generate")][-1]
    prompt = json.loads(sent.data)["prompt"]
    assert "Only the three most important points" in prompt and "hello there" in prompt
    assert "Summarize the transcript below" not in prompt
    get_settings.cache_clear()
