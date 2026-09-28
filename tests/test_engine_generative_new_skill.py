"""A second generative skill costs a file, not code.

"praise" is a skill nobody under src/ has ever heard of (not summarize
renamed), written here into a tmp_path, loaded with
workflow.skill_file.load_skill_file, bound to engine.generative.run_generative
with functools.partial, and run inside a workflow through the same
execute_step every built-in goes through. Every name this file imports
already existed before this test was written. None of it required a new
line under src/.
"""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path

import pytest
import yaml
from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.db.models.step import StepState
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.generative import run_generative
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.workflow.loader import SkillRegistry, load_workflow
from voxtrama.workflow.skill_file import load_skill_file

OLLAMA_URL = "http://127.0.0.1:11434"

_SKILL_YAML = {
    "skill": {
        "name": "praise",
        "version": "1.0.0",
        "input_schema": {"type": "object"},
        "output_schema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}, "quote": {"type": "string"}},
                    "required": ["text", "quote"],
                }
            },
            "required": ["note"],
        },
        "context_requirements": ["segments"],
        "model_class": "generative",
        "minimum_model_profile": "low",
        "evidence_required": False,
        "minimum_confidence": 0.0,
        "review_required": False,
        "retention_policy": "follows_recording",
        "output_language": "same_as_audio",
        "privacy": "any",
    },
    "prompt": "Praise the transcript below, in {language}, as JSON.\n\n{transcript}\n",
}

_WORKFLOW_YAML = """\
name: praise-only
version: 1.0.0
schema_version: v1
description: A workflow naming a skill defined nowhere under src/.
steps:
  - id: praise
    skill: praise
    skill_version: 1.0.0
"""


def _transcript() -> Transcript:
    transcript = Transcript(
        id="t1",
        recording_id="r1",
        language="en",
        model_name="whisper",
        model_revision="v1",
        hardware_profile="low",
    )
    transcript.segments = [Segment(start=0.0, end=2.0, text="what a fine sentence", confidence=1.0)]
    return transcript


def test_a_skill_written_only_as_a_file_runs_inside_a_workflow(
    tmp_path: Path, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", OLLAMA_URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    transport = install(monkeypatch)
    body = {"note": {"text": "well put", "quote": "what a fine sentence"}}
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

    skill_path = tmp_path / "praise.yaml"
    skill_path.write_text(yaml.safe_dump(_SKILL_YAML))
    skill_file = load_skill_file(skill_path)
    registry: SkillRegistry = {skill_file.skill.name: {skill_file.skill.version: skill_file.skill}}

    workflow_path = tmp_path / "praise-only.yaml"
    workflow_path.write_text(_WORKFLOW_YAML)
    workflow = load_workflow(workflow_path, registry)

    run = create_run(db_session, "praise-only", "unpinned")
    steps, rows, context, _ = prepare_run(db_session, run, workflow)
    context.transcript = _transcript()
    builtin_steps = {"praise": partial(run_generative, skill_file)}

    execute_step(context, steps[0], rows[0], builtin_steps, registry)

    assert rows[0].state == StepState.SUCCEEDED
    assert context.produced["praise"]["note"]["evidence"] == {"start": 0.0, "end": 2.0}
    assert context.models["praise"].model == "qwen-test"
