"""add error_code and error_step to run

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # error stays the message for people; these two are for a client:
    # the stable code from its closed taxonomy, and which step
    # was running when the run failed. Both nullable: a run that
    # never fails never sets them.
    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("error_code", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("error_step", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_column("error_step")
        batch_op.drop_column("error_code")
