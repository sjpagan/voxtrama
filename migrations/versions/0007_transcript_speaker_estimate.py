"""add speaker_estimate and speaker_cap to transcript

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # What diarisation estimated versus the ceiling it was given: a
    # run whose estimate exceeded the cap says so, instead of the cap
    # silently passing for the truth. Nullable: unset until diarize() runs.
    with op.batch_alter_table("transcript") as batch_op:
        batch_op.add_column(sa.Column("speaker_estimate", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("speaker_cap", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("transcript") as batch_op:
        batch_op.drop_column("speaker_cap")
        batch_op.drop_column("speaker_estimate")
