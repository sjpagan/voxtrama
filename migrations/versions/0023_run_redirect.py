"""add run_redirect and run.replaces_run_id

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-27

A regenerated job replaces the old one, which is deleted. The old
address leads to the new job through this table (db.models.run_redirect).
run.replaces_run_id names the job a regeneration or a retry will replace.
Nullable: NULL for every run written before, which replaced nothing.

downgrade() drops both: the old addresses of replaced jobs answer 404
again, and a regeneration still running then replaces nothing.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_redirect",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("target_run_id", sa.String(length=36), nullable=False),
    )
    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("replaces_run_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_column("replaces_run_id")
    op.drop_table("run_redirect")
