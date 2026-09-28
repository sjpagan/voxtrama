"""add input_sha256 and reuse_key to run_step

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-23

Two nullable columns, no server_default, for the same reason migration
0013's docstring gives for `model`/`model_revision`/`provider`/`host`/
`profile_check_skipped`: a step executed before this migration ran was
never asked what it consumed, and NULL says that better than an invented
value would.

`input_sha256` (`sa.String(64)`, a sha256 hexdigest like every other
hash column in this table) is what engine.step_hashing.input_sha256
computes: a hash of the recording plus every declared dependency's own
output, and nothing else: no run id, no row id, no timestamp. Two runs of
the same workflow over the same recording get the same value here, which
is the one property the reuse cascade depends on. `reuse_key` folds
`input_sha256` together with the identity of whoever would reuse the
output (skill, skill_version, hardware_profile, generative_model) and
answers a different question: "can this exact output be reused?", not
"did my inputs change?". Kept as two columns rather than one, because
conflating them would make a change that only affects reuse (a different
hardware profile) look, to the cascade, like a change to the inputs
themselves.

Both stay nullable forever, not just until every pre-0015 row is
backfilled, for the same two reasons `run_step`'s five columns from
migration 0013 do: a step written before this migration exists has
nothing to report, and a step the engine skipped for its condition never
reached the point where these are computed at all. It consumed nothing,
which NULL says correctly and an invented hash would not.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.add_column(sa.Column("input_sha256", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("reuse_key", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.drop_column("reuse_key")
        batch_op.drop_column("input_sha256")
