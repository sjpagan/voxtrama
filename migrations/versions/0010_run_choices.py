"""add choices to run

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # No server_default: a run written before this column never chose
    # anything, and NULL says that better than "{}" would. A run.choices that reads
    # as "chose nothing" must not be mistaken for "chose an empty set of
    # per-step skills" (workflow.choices.RunChoices' own distinction).
    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("choices", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_column("choices")
