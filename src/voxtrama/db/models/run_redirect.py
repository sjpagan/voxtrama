"""Where the address of a job that was replaced now leads.

A regenerated job that finishes well replaces the old one,
which is deleted, and the old job's address leads to the new one. The old
Run row is gone, so the pair is kept here: `run_id` is the address that
no longer has a job, `target_run_id` the job that took its place. A plain
string, not a foreign key: the target may itself be replaced later, and
housekeeping.removal moves every pair that pointed at it along.
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from voxtrama.db.models.run import Base


class RunRedirect(Base):
    """One replaced job's address, and the job it now leads to."""

    __tablename__ = "run_redirect"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    target_run_id: Mapped[str] = mapped_column(String(36))
