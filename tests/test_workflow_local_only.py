"""A workflow or a step keeps content on the machine, even for a skill that says `any`."""

from __future__ import annotations

import pytest
from fakes.http_transport import install
from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.models.transcript import Segment, Transcript
from voxtrama.engine.builtin import BUILTIN_SKILLS, BUILTIN_STEPS
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.preparation import execute_step, prepare_run
from voxtrama.providers.base import PrivacyViolation
from voxtrama.workflow.definition import Step, Workflow
from voxtrama.workflow.privacy import kept_local, local_only_steps
from voxtrama.workflow.rejection import ChoicesRejected
from voxtrama.workflow.skill import Privacy

REMOTE = "https://ollama.example.com"


def _workflow(*steps: Step, privacy: Privacy = Privacy.ANY) -> Workflow:
    return Workflow(
        name="kept",
        version="1.0.0",
        schema_version="v1",
        description="t",
        privacy=privacy,
        steps=list(steps),
    )


def _summarize(privacy: Privacy | None = None) -> Step:
    return Step(id="summarize", skill="summarize", skill_version="1.0.0", privacy=privacy)


@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", REMOTE)
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    get_settings.cache_clear()
    yield install(monkeypatch)
    get_settings.cache_clear()


def test_a_workflow_kept_local_refuses_a_remote_server_before_any_call(
    db_session: Session, remote
) -> None:
    run = create_run(db_session, "kept", "unpinned")

    with pytest.raises(ChoicesRejected, match="workflow kept"):
        prepare_run(db_session, run, _workflow(_summarize(), privacy=Privacy.LOCAL_ONLY))

    assert remote.calls == []


def test_a_single_step_can_be_kept_local_on_its_own(db_session: Session, remote) -> None:
    run = create_run(db_session, "kept", "unpinned")

    with pytest.raises(ChoicesRejected, match="step summarize"):
        prepare_run(db_session, run, _workflow(_summarize(Privacy.LOCAL_ONLY)))


def test_the_call_itself_is_the_last_guard(db_session: Session, monkeypatch) -> None:
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("VOXTRAMA_OLLAMA_MODEL", "qwen-test")
    get_settings.cache_clear()
    transport = install(monkeypatch)
    step = _summarize(Privacy.LOCAL_ONLY)
    _, rows, context, _ = prepare_run(
        db_session, create_run(db_session, "kept", "unpinned"), _workflow(step)
    )
    context.transcript = Transcript(
        id="t1", recording_id="r1", language="en", model_name="w", model_revision="v1"
    )
    context.transcript.segments = [Segment(start=0.0, end=2.0, text="hi", confidence=1.0)]
    monkeypatch.setenv("VOXTRAMA_OLLAMA_URL", REMOTE)  # the server moved after the check
    get_settings.cache_clear()

    with pytest.raises(PrivacyViolation, match="step summarize is local_only"):
        execute_step(context, step, rows[0], BUILTIN_STEPS, BUILTIN_SKILLS)
    assert transport.calls == []
    get_settings.cache_clear()


def test_it_only_narrows_and_the_manifest_lists_what_ran_kept_local() -> None:
    transcribe = Step(id="transcribe", skill="transcribe", skill_version="1.0.0")
    open_workflow = _workflow(transcribe, _summarize(Privacy.ANY))
    kept_workflow = _workflow(transcribe, _summarize(), privacy=Privacy.LOCAL_ONLY)

    assert kept_local(open_workflow) == {}
    assert local_only_steps(open_workflow, BUILTIN_SKILLS) == ["transcribe"]
    assert kept_local(kept_workflow) == {
        "transcribe": "workflow kept",
        "summarize": "workflow kept",
    }
    assert local_only_steps(kept_workflow, BUILTIN_SKILLS) == ["transcribe", "summarize"]
