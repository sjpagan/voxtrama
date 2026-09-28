"""add job_timeout_seconds to run

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # The job_timeout actually granted to this run's queue job,
    # computed from its Recording's duration. Nullable: a run created
    # without a Recording yet has nothing to compute it from.
    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("job_timeout_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_column("job_timeout_seconds")
