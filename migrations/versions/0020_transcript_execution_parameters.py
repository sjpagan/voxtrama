"""add cpu_threads and num_workers to transcript

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-25

Two nullable columns, no server_default, for
the same reason migration 0014's own comment gives for
produced_by_run_id/produced_by_step_id: a transcript written before this
migration ran was never asked what it actually used, and NULL says that
better than an invented value would.

These record the *effective* cpu_threads/num_workers transcription.asr's
transcribe() handed to WhisperModel: resolve_engine_resources's own
return value, which can differ from Settings.cores_per_chunk/
.parallel_chunks when a run fell back to this machine's own tuning
proposal instead of a configured number. Without them, two manifests that
differ only in parallelism compare identical, and the comparison's diff
cannot explain why one run took twice as long as the other.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("transcript") as batch_op:
        batch_op.add_column(sa.Column("cpu_threads", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("num_workers", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("transcript") as batch_op:
        batch_op.drop_column("num_workers")
        batch_op.drop_column("cpu_threads")
