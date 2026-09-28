"""engine.generative wired into a full run: the context budget reaches the manifest,
and a proven input truncation fails the run instead of delivering a partial
result as complete.

Follows test_engine_anchoring_run.py's own pattern: BUILTIN_STEPS and
BUILTIN_SKILLS monkeypatched to a skill defined only in this file, driven
through the real execute_run so run.error_code and the written manifest
are the same ones a person would read.
"""

from __future__ import annotations

import json

import pytest
from fakes.http_transport import FakeResponse, install
from sqlalchemy.orm import Session

from voxtrama.config.paths import get_paths
from voxtrama.config.settings import get_settings
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.context_budget import FALLBACK_MAX_CTX, compute_context_budget
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.generative import run_generative
from voxtrama.engine.run import execute_run
from voxtrama.manifest.schema import Manifest
from voxtrama.manifest.writer import manifest_path
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.skill import ModelClass, ModelProfile, Privacy, Skill
from voxtrama.workflow.skill_file import SkillFile

OLLAMA_URL = "http://127.0.0.1:11434"

_SKILL = Skill(
    name="note",
    version="1.0.0",
    input_schema={"type": "object"},
    output_schema={"type": "object"},
    model_class=ModelClass.GENERATIVE,
    minimum_model_profile=ModelProfile.LOW,
    evidence_required=False,
    minimum_confidence=0.0,
    review_required=False,
    retention_policy="follows_recording",
    privacy=Privacy.ANY,
)
_SKILL_FILE = SkillFile(skill=_SKILL, prompt="Say something about {transcript}, in {language}.\n")


def _workflow(step: Step) -> Workflow:
    return Workflow(
        name="test-workflow", version="1.0.0", schema_version="v1", description="test", steps=[step]
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


def _install(monkeypatch: pytest.MonkeyPatch) -> None:
    def _run(ctx: ExecutionContext) -> dict:
        ctx.transcript = _transcript()
        return run_generative(_SKILL_FILE, ctx)

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"note": _run})
    monkeypatch.setattr(engine_run, "BUILTIN_SKILLS", {"note": {"1.0.0": _SKILL}})
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", OLLAMA_URL)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")


def _read_manifest(run_id: str) -> Manifest:
    path = manifest_path(get_paths(get_settings().data_dir).runs_dir, run_id)
    return Manifest.model_validate_json(path.read_text())


def _requested_num_ctx() -> int:
    """num_ctx run_generative will ask for on this prompt (no InstallationConfig
    here, so it falls back to FALLBACK_MAX_CTX). Computed, not guessed, so the
    truncation below is proven against the real ceiling.
    """
    prompt = _SKILL_FILE.prompt.format(transcript="hello there", language="en")
    return compute_context_budget(prompt, FALLBACK_MAX_CTX).num_ctx


def test_a_clean_run_writes_its_context_budget_to_the_manifest(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch)
    transport = install(monkeypatch)
    transport.route(
        f"{OLLAMA_URL}/api/generate",
        FakeResponse(200, json.dumps({"response": "{}", "done_reason": "stop"}).encode()),
    )
    transport.route(
        f"{OLLAMA_URL}/api/tags", FakeResponse(200, json.dumps({"models": []}).encode())
    )
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="note", skill="note", skill_version="1.0.0")

    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.SUCCEEDED
    manifest_step = next(s for s in _read_manifest(run.id).steps if s.step_id == "note")
    assert manifest_step.context_window_tokens is not None
    assert manifest_step.context_window_at_risk is False
    assert manifest_step.output_resumptions == 0


def test_a_prompt_read_only_partially_fails_the_run_instead_of_finishing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """prompt_eval_count landing at the requested num_ctx proves the
    truncation, never a comparison against the (deliberately oversized) estimate.
    """
    _install(monkeypatch)
    transport = install(monkeypatch)
    body = {
        "response": "irrelevant",
        "done_reason": "stop",
        "prompt_eval_count": _requested_num_ctx(),
    }
    transport.route(f"{OLLAMA_URL}/api/generate", FakeResponse(200, json.dumps(body).encode()))
    transport.route(
        f"{OLLAMA_URL}/api/tags", FakeResponse(200, json.dumps({"models": []}).encode())
    )
    created = create_run(db_session, "test-workflow", "unpinned")
    step = Step(id="note", skill="note", skill_version="1.0.0")

    run = execute_run(db_session, created.id, workflow=_workflow(step))

    assert run.state == JobState.FAILED
    assert run.error_code == "generation_truncated"
    assert run.error_step == "note"
    manifest_step = next(s for s in _read_manifest(run.id).steps if s.step_id == "note")
    assert manifest_step.context_window_tokens is not None
    assert manifest_step.output_resumptions is None
