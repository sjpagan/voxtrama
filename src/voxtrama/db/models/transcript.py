"""SQLAlchemy models for a Transcript and its Segments.

A Transcript is the ASR result for one Recording, and a Segment is one of
its lines. The model revision (not "latest") is recorded on the
Transcript, since the same profile can otherwise give a different result
months apart.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voxtrama.db.models.person import Person
from voxtrama.db.models.run import Base


class Transcript(Base):
    """The ASR output for one Recording: which model produced it, and how."""

    __tablename__ = "transcript"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recording_id: Mapped[str] = mapped_column(String(36), ForeignKey("recording.id"))
    language: Mapped[str] = mapped_column(String)
    model_name: Mapped[str] = mapped_column(String)
    model_revision: Mapped[str] = mapped_column(String)
    hardware_profile: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    # What diarisation heard versus what it was allowed to report:
    # null until diarize() runs. speaker_estimate can exceed
    # speaker_cap: that is the run declaring a silent cap instead of
    # having one, which a run is never allowed to do.
    speaker_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speaker_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Which run produced this Transcript, and which of its steps.
    # Nullable not because a Transcript can have no producing run (every
    # one is written by exactly one run's transcribe step), but because a
    # row written before migration 0014 was never asked to record it. NULL
    # here means "predates this column", not "produced by nothing".
    # engine.reconcile_manifest falls back to the most recent Transcript of
    # the Recording only for such a row, never as the general rule.
    produced_by_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("run.id"), nullable=True
    )
    produced_by_step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The cpu_threads/num_workers transcribe() handed WhisperModel:
    # resolve_engine_resources's own return value, which
    # can differ from Settings.cores_per_chunk/.parallel_chunks when a run
    # fell back to this machine's own tuning proposal. Nullable forever,
    # not backfilled: a row written before migration 0020 was never asked
    # to record either, for the same reason produced_by_run_id above is
    # nullable rather than guessed.
    cpu_threads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_workers: Mapped[int | None] = mapped_column(Integer, nullable=True)

    segments: Mapped[list[Segment]] = relationship(back_populates="transcript")


class Segment(Base):
    """One utterance of a Transcript, with its timing, text and speaker.

    speaker_label and person_id are two different things, kept apart on
    purpose. The label is what diarisation produces (`spk0`, `spk1`): a
    voice told apart from the others but not identified. person_id is a
    Person someone linked by hand, a separate and reversible act. The label
    survives that link rather than being overwritten by it.

    Both are nullable, and for different reasons: the label is absent until
    diarisation runs (or where it has nothing to say), person_id until a
    human says who that voice belongs to. The ForeignKey and relationship
    below arrived one migration after this column did: person_id existed
    for a while with no person table to point at yet.
    """

    __tablename__ = "segment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transcript_id: Mapped[str] = mapped_column(String(36), ForeignKey("transcript.id"))
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    speaker_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    person_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("person.id"), nullable=True
    )

    transcript: Mapped[Transcript] = relationship(back_populates="segments")
    person: Mapped[Person | None] = relationship()
