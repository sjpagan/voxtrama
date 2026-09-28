"""What a second connection sees while a run is running.

Every assertion here reads through a session of its own, because that is what
matters: a flush makes a change visible inside the transaction that made
it and nowhere else. The engine could see RUNNING for the entire length of a
run while the API, an interface, or a person with a database client saw
pending, and the CLI never noticed, because it reads progress.json.

The database is a file rather than `:memory:` for the same reason: two
connections to an in-memory SQLite are two different databases, so a test
written against one could not fail the way production did.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from voxtrama.db.models import Base
from voxtrama.db.models.run import Run
from voxtrama.engine.builtin import BUILTIN_STEPS
from voxtrama.engine.context import ExecutionContext
from voxtrama.engine.enqueue import create_run
from voxtrama.engine.run import execute_run
from voxtrama.queue.job import JobState
from voxtrama.workflow.definition import Step, Workflow


@pytest.fixture
def sessions(tmp_path) -> Iterator[sessionmaker]:
    """A session factory over a database two connections can both reach."""
    engine = create_engine(f"sqlite:///{tmp_path / 'voxtrama.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def _workflow(*skills: str) -> Workflow:
    return Workflow(
        name="visibility",
        version="1.0.0",
        schema_version="v1",
        description="a workflow used to observe a run from outside",
        steps=[Step(id=skill, skill=skill, skill_version="1.0.0") for skill in skills],
    )


@pytest.fixture
def watching_step(monkeypatch, sessions):
    """Register a step that, mid-run, asks a second connection what it sees."""
    seen: dict[str, object] = {}

    def _step(ctx: ExecutionContext) -> None:
        with sessions() as watcher:
            seen["run_state"] = watcher.get(Run, ctx.run.id).state
            seen["steps"] = watcher.execute(
                text("SELECT step_id, state FROM run_step WHERE run_id = :rid ORDER BY position"),
                {"rid": ctx.run.id},
            ).all()

    monkeypatch.setitem(BUILTIN_STEPS, "watch", _step)
    return seen


def test_a_running_run_is_visible_as_running_from_outside(sessions, watching_step) -> None:
    """The defect: a run at work looked, from anywhere else, like one not started."""
    with sessions() as session:
        run_id = create_run(session, "visibility", "1.0.0").id
    with sessions() as session:
        execute_run(session, run_id, workflow=_workflow("watch"))

    assert watching_step["run_state"] == JobState.RUNNING


def test_a_running_step_is_visible_as_running_from_outside(sessions, watching_step) -> None:
    """A step that never returns has to be identifiable as the one that hung."""
    with sessions() as session:
        run_id = create_run(session, "visibility", "1.0.0").id
    with sessions() as session:
        execute_run(session, run_id, workflow=_workflow("watch"))

    assert ("watch", JobState.RUNNING) in watching_step["steps"]


def test_the_final_state_is_visible_from_outside(sessions) -> None:
    with sessions() as session:
        run_id = create_run(session, "visibility", "1.0.0").id
    with sessions() as session:
        execute_run(session, run_id, workflow=_workflow())

    with sessions() as watcher:
        assert watcher.get(Run, run_id).state == JobState.SUCCEEDED
