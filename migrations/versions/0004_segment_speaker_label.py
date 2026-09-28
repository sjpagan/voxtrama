"""add speaker_label to segment

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Deliberately separate from person_id: this one is the
    # anonymous voice diarisation tells apart, that one is a person a human
    # linked by hand. Nullable because a Segment exists before diarisation
    # has run, and because diarisation may have nothing to say about a
    # stretch. An invented label would read like a real one downstream.
    with op.batch_alter_table("segment") as batch_op:
        batch_op.add_column(sa.Column("speaker_label", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("segment") as batch_op:
        batch_op.drop_column("speaker_label")
