"""The state of one step inside a Run, persisted so it can be read back.

Named RunStep, not Step: `voxtrama.workflow.definition.Step` is
the *declared* step of a workflow file, this is the *execution* of one. Two
classes called Step meaning different things would cost someone an
afternoon six months from now.

The run manifest needs this to be built, and the progress display
needs it to say which step is running: both read rows, neither infers state
from logs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from voxtrama.db.models.run import Base


class StepState(StrEnum):
    """The lifecycle one RunStep goes through: its own, not the Run's.

    This used to reuse JobState (queue.job), on the reasoning that a step's
    state and a job's state are the same idea. That reasoning broke the
    moment a step could be skipped: JobState has no `skipped` value,
    and adding one there would make a Run itself representable as
    `skipped`, which corresponds to nothing. A Run either ran or it did
    not. Only one of its steps can have been beside the point.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStep(Base):
    """One step of a workflow as it was executed, with its own final state."""

    __tablename__ = "run_step"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("run.id"))
    # The id the workflow file gives this step ("transcribe"), not a uuid:
    # it is what a person reads in the file and in the manifest.
    step_id: Mapped[str] = mapped_column(String(64))
    skill: Mapped[str] = mapped_column(String(64))
    skill_version: Mapped[str] = mapped_column(String(32))
    state: Mapped[StepState] = mapped_column(String)
    # The order the engine resolved from the declared dependencies, kept so a
    # manifest can be read without re-resolving the graph.
    position: Mapped[int] = mapped_column()
    # How many times the engine invoked this step. 1 for a step
    # that never failed. More only when on_error.retry applied (which is
    # restricted to an extractive skill), but the manifest needs
    # this count regardless of which case it was.
    attempts: Mapped[int] = mapped_column(default=1)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    # Where the model that produced this step ran (migration 0013).
    # NULL for a step that never asked a model anything at all, or one
    # written before this column existed. Never an invented value. Every
    # built-in step today does ask one (transcribe, diarize, every
    # generative step). See engine.progress.record_provenance for who
    # writes these and when.
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    # The model's fingerprint: the ASR's pinned weight revision, the
    # digest a generative provider's own API reports, or None when the
    # weight source itself declares no revision to pin (diarize's ECAPA-
    # TDNN: see engine.diarize_step.run_diarize's docstring for why that
    # None is not the same None as an unrecorded row). Never the bare tag.
    model_revision: Mapped[str | None] = mapped_column(String, nullable=True)
    # "local" for a model that runs in this same process (transcribe,
    # diarize: see either one's docstring for why NULL would be
    # wrong here), "ollama" for one behind providers.ollama. NULL only for
    # a step whose provenance was never recorded, or one written before
    # this column existed.
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    # The bare host a log line is allowed to show,
    # never a URL with a credential in it. NULL for a local, in-process
    # model: there is no host to contact, which is itself the answer,
    # not an unknown value (see engine.extractive_steps.run_transcribe).
    host: Mapped[str | None] = mapped_column(String, nullable=True)
    # None means "we do not know" (before this migration, or a step whose
    # provenance was never recorded), False means "the check ran". Not
    # the same thing, and defaulting one to the other would misreport
    # which.
    profile_check_skipped: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # The sha256 of what this step *consumed* (migration 0015):
    # engine.step_hashing.input_sha256, written by engine.preparation.
    # execute_step before the step's own implementation runs. Answers "did
    # what I depend on change?": the recording plus every dependency's own
    # output_sha256, and nothing about who is asking. NULL for a step
    # skipped by its condition (it never reached execute_step, so it never
    # consumed anything), or one written before this migration.
    input_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # input_sha256 plus the identity of whoever consumes it (skill,
    # skill_version, hardware_profile, generative_model;
    # engine.step_hashing.reuse_key). Answers a different question than
    # input_sha256: "can this exact output be reused?", not "did my inputs
    # change?". Two distinct columns, not one, because the cascade and
    # the reuse read different truths. Conflating them would make a
    # workflow edit that changes nothing about the inputs invalidate a
    # cascade it should not touch.
    reuse_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # What *happened* to this step (migration 0016): the id of
    # the run engine.reuse.apply_reused_output copied this step's output
    # from, or NULL when the step ran (or was skipped) instead. Set only on
    # a row that was reused, never on the strength of run.
    # reused_from_run_id alone, which only says a run asked to reuse
    # something, not that this particular step found a match. Not a new
    # StepState value: a reused step's own `state` stays
    # `succeeded`, since it produced a validated, re-anchored output. Every
    # `steps.<id>.state == 'succeeded'` a workflow condition already reads
    # would otherwise silently stop matching a step that was reused.
    reused_from_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("run.id"), nullable=True
    )
    # Migration 0019: the num_ctx a generative call
    # asked Ollama for, and whether that number already conceded it might
    # be too small for the prompt (need > max_ctx: the call still
    # runs, at the ceiling, but the risk gets written down here rather than
    # discovered later). NULL for a step that never asked a model anything.
    context_window_tokens: Mapped[int | None] = mapped_column(nullable=True)
    context_window_at_risk: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # How many times engine.generation_resume had to continue this call
    # past Ollama's own output cap before it could return
    # something whole. NULL alongside the two columns above for the same
    # reason. 0 means the first answer already came back complete.
    output_resumptions: Mapped[int | None] = mapped_column(nullable=True)
    # Migration 0024: how many windows a generative step read the
    # transcript in (engine.transcript_windows). 1 for one that fit whole,
    # NULL for a step that asked no model anything.
    transcript_windows: Mapped[int | None] = mapped_column(nullable=True)
