"""create run_step

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # One row per step of a run, written before the step starts rather than
    # after it ends: a step that never finishes has to be visible too, or a
    # run killed halfway looks like a run that never got there.
    op.create_table(
        "run_step",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("run.id"), nullable=False),
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("skill", sa.String(length=64), nullable=False),
        sa.Column("skill_version", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
    )
    op.create_index("ix_run_step_run_id", "run_step", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_step_run_id", table_name="run_step")
    op.drop_table("run_step")
