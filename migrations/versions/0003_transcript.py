"""create transcript and segment tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transcript",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "recording_id", sa.String(length=36), sa.ForeignKey("recording.id"), nullable=False
        ),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("model_revision", sa.String(), nullable=False),
        sa.Column("hardware_profile", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "segment",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "transcript_id", sa.String(length=36), sa.ForeignKey("transcript.id"), nullable=False
        ),
        sa.Column("start", sa.Float(), nullable=False),
        sa.Column("end", sa.Float(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        # No foreign key: Person does not exist yet at this revision. Nullable,
        # and always written as null here. See db/models/transcript.py.
        sa.Column("person_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("segment")
    op.drop_table("transcript")
