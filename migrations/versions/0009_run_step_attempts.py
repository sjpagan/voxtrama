"""add attempts to run_step

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # How many times the engine actually invoked this step: 1 for a
    # step that never failed, more only when on_error.retry applied. A
    # server default backfills every row a previous run already wrote,
    # which was exactly one attempt each: there was no retry to record it.
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.add_column(sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.drop_column("attempts")
