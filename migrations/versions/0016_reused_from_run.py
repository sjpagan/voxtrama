"""add reused_from_run_id to run and run_step

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-23

Two nullable columns, no server_default, for the same reason migration
0015's docstring gives for `input_sha256`/`reuse_key`: a run or a step
written before this migration ran was never asked to reuse anything, and
NULL says that better than an invented value would.

Both are `sa.String(36)`, matching `run.id`'s own column type, and both
are real foreign keys to `run.id`, not just same-shaped strings, for the
same reason migration 0014's `produced_by_run_id` is one: the reuse
engine needs to resolve "the run this reuse came from" by more than a
same-shaped guess.

They answer two different questions:

`run.reused_from_run_id` is what a run *asked for*: the `--reuse-from`
argument a request was made with (engine.enqueue.create_run writes it, in
the same commit that creates the Run, the same reasoning migration 0010's
`choices` and migration 0011's `created_by` already give for writing a
request's own facts once, at creation, never patched in afterwards).

`run_step.reused_from_run_id` is what *actually happened*, step by step.
It is set only on a row engine.reuse.apply_reused_output actually reused, left
NULL on every row the engine recomputed instead. A run can ask to reuse
and still recompute every step, when nothing in the source run's
`reuse_key`s matches. The two columns must be able to disagree, or asking
could never be told apart from succeeding.

Deliberately not a new `StepState` value: a workflow can already
condition on `steps.<id>.state`, and every `== 'succeeded'` written
against that column today would have to learn about a fourth value in
silence. A reused step *is* `succeeded` (it produced a validated,
re-anchored output). Reuse is a fact about how it got there, carried on
this column instead.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("reused_from_run_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_run_reused_from_run_id_run", "run", ["reused_from_run_id"], ["id"]
        )
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.add_column(sa.Column("reused_from_run_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_run_step_reused_from_run_id_run", "run", ["reused_from_run_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.drop_constraint("fk_run_step_reused_from_run_id_run", type_="foreignkey")
        batch_op.drop_column("reused_from_run_id")
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_constraint("fk_run_reused_from_run_id_run", type_="foreignkey")
        batch_op.drop_column("reused_from_run_id")
