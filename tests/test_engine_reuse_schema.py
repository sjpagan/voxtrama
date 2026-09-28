"""A reused output is validated against the skill as it is now, not as it was.

A user's copy of a skill file may change at any time, so two
runs naming the same skill_version can meet two different output_schemas.
That is why engine.reuse validates a reused output exactly like a
freshly produced one. Without that check the reuse
branch would be the one path into a later step that never passes a
schema.

Split from test_engine_reuse.py for the project's size limit, the same
reason test_engine_reuse_no_match.py is its own file.
"""

from __future__ import annotations

import pytest
from fakes.reuse_steps import install, workflow
from fakes.workflow import fake_skill
from sqlalchemy.orm import Session

from voxtrama.db.models.recording import Recording
from voxtrama.db.models.run import RunState
from voxtrama.engine import run as engine_run
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run


def _recording(session: Session) -> Recording:
    recording = Recording(
        original_filename="meeting.wav",
        stored_path="recordings/meeting.wav",
        content_sha256="4" * 64,
        duration_seconds=1.0,
        media_format="wav",
    )
    session.add(recording)
    session.flush()
    return recording


def _demand_a_field_t_never_produces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-register "t" with an output_schema its own recorded output cannot satisfy."""
    narrowed = fake_skill("t").model_copy(
        update={"output_schema": {"type": "object", "required": ["absent_on_purpose"]}}
    )
    skills = {name: {"1.0.0": fake_skill(name)} for name in ("d", "s1", "s2")}
    skills["t"] = {"1.0.0": narrowed}
    monkeypatch.setattr(engine_run, "BUILTIN_SKILLS", skills)


def test_a_reused_output_that_no_longer_fits_its_schema_fails_the_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"t": 0, "d": 0, "s1": 0, "s2": 0}
    install(monkeypatch, calls)
    recording = _recording(db_session)

    created1 = create_run(db_session, "test-workflow", "unpinned", recording_id=recording.id)
    run1 = execute_run(db_session, created1.id, workflow=workflow("s1"))
    assert run1.state == RunState.SUCCEEDED

    _demand_a_field_t_never_produces(monkeypatch)
    created2 = create_run(
        db_session,
        "test-workflow",
        "unpinned",
        recording_id=recording.id,
        reused_from_run_id=run1.id,
    )
    run2 = execute_run(db_session, created2.id, workflow=workflow("s1"))

    # Refused, not adopted: and refused without rerunning "t" either.
    assert run2.state == RunState.FAILED
    assert run2.error_step == "t"
    assert calls["t"] == 1
