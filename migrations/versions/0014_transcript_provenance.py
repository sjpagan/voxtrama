"""add produced_by_run_id and produced_by_step_id to transcript

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-23

Two nullable columns, no server_default, for the same reason migration
0013's docstring gives for `model`/`model_revision`/`provider`/`host`/
`profile_check_skipped` on `run_step`: a Transcript written before this
migration ran was never asked which run produced it, and NULL says that
better than an invented value would.

`produced_by_run_id` (`sa.String(36)`, matching `run.id`'s own column
type) is a real foreign key to `run.id`, not just a same-shaped string:
`engine.reconcile_manifest.recording_and_transcript` needs to resolve
"the Transcript this run produced" by more than a recency guess, and a
column that cannot point at a row that was never a Run would defeat that
before it started. `produced_by_step_id` (`sa.String(64)`, matching
`run_step.step_id`'s own column type) has no foreign key of its own:
`run_step` is keyed by `(run_id, step_id)` together, not by `step_id`
alone, so `produced_by_run_id` already carries the half of that pair a
foreign key can usefully constrain.

Both stay nullable forever, not just until every pre-0014 row is
backfilled: a Recording can be transcribed more than once, and the first
transcribe that ever ran on a row already in the database has no run to
report either, for the same reason `run_step`'s five columns do not
either. NULL here means "written before this migration, or by a caller
this migration does not know about", never "produced by no run at all",
since every Transcript is produced by exactly one run's `transcribe` step.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("transcript") as batch_op:
        batch_op.add_column(sa.Column("produced_by_run_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("produced_by_step_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_transcript_produced_by_run_id_run",
            "run",
            ["produced_by_run_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("transcript") as batch_op:
        batch_op.drop_constraint("fk_transcript_produced_by_run_id_run", type_="foreignkey")
        batch_op.drop_column("produced_by_step_id")
        batch_op.drop_column("produced_by_run_id")
