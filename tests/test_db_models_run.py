"""RunState: its own lifecycle, separate from JobState (see its docstring)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from voxtrama.db.models.run import Run, RunState, is_final


def test_run_state_values_are_stable_strings():
    """A Run saved before RunState existed must read back identically: the four
    states RunState shares with the old JobState-backed column keep the
    exact same string values, and the two new ones join them.
    """
    assert RunState.PENDING == "pending"
    assert RunState.RUNNING == "running"
    assert RunState.SUCCEEDED == "succeeded"
    assert RunState.FAILED == "failed"
    assert RunState.CANCELLED == "cancelled"
    assert RunState.INTERRUPTED == "interrupted"


def test_every_run_state_is_classified_as_final_or_not():
    """Fails if a new RunState value is added without deciding is_final for
    it: comparing against every current member (`for state in RunState`)
    means a new one shows up as an unexpected key here, rather than
    silently defaulting to "not final".
    """
    assert {state: is_final(state) for state in RunState} == {
        RunState.PENDING: False,
        RunState.RUNNING: False,
        RunState.SUCCEEDED: True,
        RunState.FAILED: True,
        RunState.CANCELLED: True,
        RunState.INTERRUPTED: True,
    }


def test_is_final_still_reads_correctly_after_a_commit(db_session: Session) -> None:
    """The trap this guards against: SQLAlchemy's post-commit attribute
    expiry (the session default) reloads `state` as a plain str, not a
    RunState. A test that never commits would never see it. Production,
    which always commits, would.
    """
    run = Run(workflow_name="demo", workflow_version="1.0.0", state=RunState.CANCELLED)
    db_session.add(run)
    db_session.commit()

    assert is_final(run.state)
