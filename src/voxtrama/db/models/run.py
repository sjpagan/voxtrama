"""SQLAlchemy model for a Run: the execution of a Workflow on a Recording."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all persisted models."""


class RunState(StrEnum):
    """The lifecycle a Run goes through: its own, not the queue job's.

    This used to reuse JobState (queue.job), on the reasoning that a run's
    state and its queue job's state are the same idea. That reasoning is
    what StepState's docstring (db.models.step) already warned
    against for a step: JobState has no `interrupted` value, and adding
    one there would make a queue job itself representable as
    `interrupted`, which corresponds to nothing. A job runs, succeeds,
    fails or is cancelled inside the queue. Only a Run can be interrupted,
    by a worker that stops existing mid-execution.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


_FINAL_RUN_STATES = frozenset(
    {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED, RunState.INTERRUPTED}
)


def is_final(state: RunState | str) -> bool:
    """Whether a run in `state` will never change state again.

    A module-level function, not a property on RunState: `Run.state` is a
    plain `String` column, and SQLAlchemy's post-commit attribute expiry
    (the session default) reloads it as a plain str, which has no
    `.is_final`: a run.state.is_final that only a test without a commit
    in it would ever exercise. Accepting `str` here makes that the normal
    case, not a pitfall every caller has to remember.

    The one place finality is decided: manifest.sections.run_info,
    cli.progress_view and engine.failure.fail_run used to keep their own
    hand-written list of terminal states, and neither of the first two
    included `cancelled`, so a run that ended that way left `voxtrama
    run` waiting forever and its manifest never final. All three now call
    this instead of writing a fourth list.
    """
    return RunState(state) in _FINAL_RUN_STATES


class Run(Base):
    """A single execution of a Workflow, tracked from pending to a final state."""

    __tablename__ = "run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_name: Mapped[str] = mapped_column(String)
    workflow_version: Mapped[str] = mapped_column(String)
    # Nullable: a Run's Recording is set by the entrypoint that creates it
    # (the CLI and the API), but nothing in this model requires one to
    # exist yet. A URL ingest may populate it later.
    recording_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("recording.id"), nullable=True
    )
    state: Mapped[RunState] = mapped_column(String)
    # Set by engine.enqueue.enqueue_run, in the same transaction that
    # creates the Run (before submit() is called, not from its return
    # value), so a Run is never visible as `pending`/`running` without
    # already knowing which queue job is executing it.
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # The job_timeout granted to this run's queue job, computed from
    # its Recording's duration when one exists. Null when there was no
    # Recording to compute it from yet. The queue backend then falls back
    # to its own default rather than being handed nothing.
    job_timeout_seconds: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # error is for people: a message worth reading in a log or a terminal.
    # error_code and error_step are for a client: a stable string from a
    # closed taxonomy ("internal" unless the exception that failed the run
    # carries its own) and which step, if any, was running when it did.
    # Both nullable: a run that never fails never sets them, and a failure
    # before any step started names none.
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_step: Mapped[str | None] = mapped_column(String, nullable=True)
    # What this run chose, as workflow.choices.RunChoices.model_dump():
    # hardware_profile, generative_model, step_skills. A single JSON
    # column, not three columns or a table of its own. step_skills is a
    # mapping and would need a JSON column or a table either way, a table
    # for a handful of rows per run costs more than it is worth, and the
    # three choices are validated together (engine.choice_check) and
    # written together, so nothing is served by storing them apart. This is
    # the project's first JSON column: nothing here follows a precedent.
    # Nullable, no server_default: a run written before choices existed chose nothing,
    # and NULL says that. {} would claim an empty set of choices instead.
    choices: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    # Set by engine.enqueue.create_run, from a user id the caller resolved
    # and passed in: engine is core and cannot call db.people.local_user
    # itself. Nullable, no server_default, same reasoning
    # migration 0010's own comment gives for `choices`: a run written
    # before migration 0011 has no author, and NULL says that better than
    # a value invented for every row that came before it.
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("user.id"), nullable=True)
    # What this run *asked for* (migration 0016): the `--reuse-from`
    # argument a request was made with, written by engine.enqueue.create_run
    # in the same commit that creates the Run, the same reasoning `choices`
    # and `created_by` above already follow. Never patched in afterwards.
    # A run can ask to reuse and still recompute every step, when nothing in
    # the source run's reuse_keys matches: this column says what was asked,
    # not what happened. See run_step.reused_from_run_id (db.models.step)
    # for what happened, step by step.
    reused_from_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("run.id"), nullable=True
    )
    # The name a person gives *this run* in the new-job form's `Job name`
    # field, set at request time by api.routes.run_create. Lives on Run,
    # not Recording, even though the two would agree most of the time:
    # rerunning the same audio under a second workflow is a second Run
    # ("per questa esecuzione, su questo audio": for this run, on this
    # audio), and the two may answer "what do I call this attempt"
    # differently. Recording.original_filename already answers "what do I call this
    # audio", and a label on Run does not have to repeat or override it.
    # Nullable: a run nobody named stays nameless, not "". Free text, never
    # checked and never in logs.context's field set.
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    # The job this one takes the place of once it succeeds, set only
    # by Regenerate and Retry (housekeeping.replacement). Not the same as
    # reused_from_run_id, which `voxtrama run --reuse-from` also sets
    # without asking for anything to be replaced. No foreign key: the job
    # named here is deleted by the very success this column waits for.
    replaces_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # The context the engine deduced from the transcript when
    # none was declared (engine.context_deduction). Text, shown marked as
    # deduced. NULL when a context was declared or no model step ran.
    deduced_context: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
