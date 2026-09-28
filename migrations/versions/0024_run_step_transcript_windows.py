"""add transcript_windows to run_step

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-27

How many windows a generative step read the transcript in
(engine.transcript_windows). Nullable, no server_default: a step written
before this migration was never split, and NULL says it was not measured
rather than an invented 1.

downgrade() drops the column, and with it the count for every step that
had one: a downgrade's data loss is said, not left implicit.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.add_column(sa.Column("transcript_windows", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.drop_column("transcript_windows")
