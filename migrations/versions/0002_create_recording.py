"""create recording table and run.recording_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recording",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("stored_path", sa.String(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("media_format", sa.String(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
    )
    # batch mode: SQLite cannot ALTER TABLE ADD a foreign key directly, so
    # Alembic recreates the table under the hood instead.
    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("recording_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_run_recording_id_recording", "recording", ["recording_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_constraint("fk_run_recording_id_recording", type_="foreignkey")
        batch_op.drop_column("recording_id")
    op.drop_table("recording")
