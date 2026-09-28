"""add deduced_context to run

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-27

The context the engine deduces from the transcript when the
job declared none. Nullable, no server_default: a run written before this
migration deduced nothing, and NULL says that.

downgrade() drops the column, and with it every deduced context.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("deduced_context", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_column("deduced_context")
