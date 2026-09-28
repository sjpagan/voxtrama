"""add label to run

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-26

The name a person gives one run in the new-job form's `Job name` field.
See the db.models.run.Run.label comment for why it lives here rather
than on Recording. Nullable, no server_default, same reasoning migration
0010 gives for `choices`: a run written before this migration never had
anything to name, and NULL says that, not "".

downgrade() drops the column, taking every label given this way with it,
because a downgrade's data loss should be said, not
discovered, same as migration 0021 says of itself for speaker_name.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("label", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_column("label")
