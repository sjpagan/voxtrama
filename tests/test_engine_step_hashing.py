"""input_sha256 and reuse_key: what changes each value, and what must not.

Runs a two-step workflow through engine.run.execute_run with the same
lightweight fakes test_engine_conditional.py uses (fakes.workflow.fake_skill,
a monkeypatched BUILTIN_STEPS), not faster-whisper or diarization, since
neither is what these tests are about. Every test here varies exactly one thing
between two runs and holds the rest equal: a synthetic value that happens
to never differ is the failure this project finds most often, and the
property that decides whether step reuse works at all (no run id, row id or
timestamp reaching either hash) only shows up by comparing two runs.

The skipped-condition case lives in test_engine_step_hashing_skip.py,
split apart for the project's size limit, the same reason
test_engine_step_model_provenance.py gives for its own split.
"""

from __future__ import annotations

import pytest
from fakes.workflow import fake_skill
from sqlalchemy import select
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.step import RunStep
from voxtrama.engine import run as engine_run
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.workflow.choices import RunChoices
from voxtrama.workflow.definition import Step, Workflow


def _workflow() -> Workflow:
    return Workflow(
        name="test-workflow",
        version="1.0.0",
        schema_version="v1",
        description="A workflow built in a test.",
        steps=[
            Step(id="a", skill="a", skill_version="1.0.0"),
            Step(id="b", skill="b", skill_version="1.0.0", depends_on=["a"]),
        ],
    )


def _install(monkeypatch: pytest.MonkeyPatch, *, a_value: str = "a", b_value: str = "b") -> None:
    def _step_a(ctx: ExecutionContext) -> dict:
        return {"value": a_value}

    def _step_b(ctx: ExecutionContext) -> dict:
        return {"value": b_value}

    monkeypatch.setattr(engine_run, "BUILTIN_STEPS", {"a": _step_a, "b": _step_b})
    monkeypatch.setattr(
        engine_run, "BUILTIN_SKILLS", {name: {"1.0.0": fake_skill(name)} for name in ("a", "b")}
    )


def _recording(session: Session, sha256: str) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256=sha256,
        duration_seconds=1.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def _rows(session: Session, run_id: str) -> dict[str, RunStep]:
    result = session.scalars(select(RunStep).where(RunStep.run_id == run_id)).all()
    return {row.step_id: row for row in result}


def _run(
    db_session: Session, recording: Recording, choices: RunChoices | None = None
) -> dict[str, RunStep]:
    created = create_run(
        db_session, "test-workflow", "unpinned", recording_id=recording.id, choices=choices
    )
    run = execute_run(db_session, created.id, workflow=_workflow())
    return _rows(db_session, run.id)


def test_two_runs_of_the_same_workflow_over_the_same_recording_hash_identically(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No run id, row id or timestamp reaches either hash: prove it by hashing twice."""
    _install(monkeypatch)
    recording = _recording(db_session, "1" * 64)

    first = _run(db_session, recording)
    second = _run(db_session, recording)

    assert first["a"].id != second["a"].id
    for step_id in ("a", "b"):
        assert first[step_id].input_sha256 == second[step_id].input_sha256
        assert first[step_id].reuse_key == second[step_id].reuse_key
        assert first[step_id].input_sha256 is not None


def test_changing_generative_model_changes_reuse_key_but_not_input_sha256(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch)
    recording = _recording(db_session, "2" * 64)

    plain = _run(db_session, recording)
    chosen = _run(db_session, recording, choices=RunChoices(generative_model="qwen-test"))

    for step_id in ("a", "b"):
        assert plain[step_id].input_sha256 == chosen[step_id].input_sha256
        assert plain[step_id].reuse_key != chosen[step_id].reuse_key


def test_changing_the_recordings_content_sha256_changes_both(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch)
    first_recording = _recording(db_session, "3" * 64)
    second_recording = _recording(db_session, "4" * 64)

    first = _run(db_session, first_recording)
    second = _run(db_session, second_recording)

    for step_id in ("a", "b"):
        assert first[step_id].input_sha256 != second[step_id].input_sha256
        assert first[step_id].reuse_key != second[step_id].reuse_key


def test_changing_what_a_dependency_produced_changes_the_dependents_input_sha256(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = _recording(db_session, "5" * 64)

    _install(monkeypatch, a_value="first")
    first = _run(db_session, recording)

    _install(monkeypatch, a_value="second")
    second = _run(db_session, recording)

    # "a" has no dependency of its own: what it consumes never changed.
    assert first["a"].input_sha256 == second["a"].input_sha256
    # "b" depends on "a", and "a" produced something different this time.
    assert first["b"].input_sha256 != second["b"].input_sha256
