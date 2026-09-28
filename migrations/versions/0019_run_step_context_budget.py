"""add context budget to run_step

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-24

Three nullable columns, no server_default, for the
same reason migration 0013's own comment gives for model/model_revision/
provider/host: a step executed before this migration never computed a
context budget at all, and NULL says that, rather than an invented 0 or
False standing in for it.

`context_window_tokens` and `context_window_at_risk`: the num_ctx a
generative call actually asked Ollama for, and whether that number already
conceded the estimate did not fit under the model's own ceiling.
`output_resumptions`: how many times the call had to continue past
Ollama's own output cap before it returned something whole.

All three NULL together for the same two cases migration 0013 already
distinguishes for provenance: a step that never asked a model anything
(extractive, or skipped), or one written before this migration ran.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.add_column(sa.Column("context_window_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("context_window_at_risk", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("output_resumptions", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.drop_column("output_resumptions")
        batch_op.drop_column("context_window_at_risk")
        batch_op.drop_column("context_window_tokens")
