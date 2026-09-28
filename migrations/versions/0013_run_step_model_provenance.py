"""add model provenance to run_step

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-23

Five nullable columns, no server_default, for the same reason migration
0010's comment gives for `choices`, 0011's for `created_by` and 0012's for
`source_title`/`source_url`: a step executed before this migration ran
never had a model to record where it ran, and NULL says that better than
an invented value would.

`model` and `model_revision`: `model_revision` carries
the model's own fingerprint: for the ASR it is the pinned weight
revision (transcription.asr._MODEL_REVISIONS), for a generative provider
it is the digest the provider's own API reports. One column for both,
because they answer the same question (which exact weight ran), never two
that could disagree.

`provider` and `host`: where the model ran.
`provider` is never NULL for a step whose provenance was actually
recorded: "local" for a model running in this same process (transcribe),
never NULL standing in for "ran locally", which would be
indistinguishable from "never recorded" on a step-by-step read of the
manifest. `host` can be NULL, but only as an answer: an in-process model
has no host to contact. Never a URL either way (`providers.ollama.
classify_host` already strips any credential before this ever sees the
value), only the bare host a log line is allowed to
show.

`profile_check_skipped` is deliberately `Boolean` and nullable, and the two
falsy-looking values it can hold mean different things: `NULL` is "we do
not know" (a step whose provenance was never recorded at all), `False` is
"the check ran". That holds for a local Ollama call and for transcribe alike,
since neither has the verification gap "skipped" was built for in
the first place: that gap is a *remote* provider's memory being
unreadable from here, not a fact about any local model. Conflating NULL
and `False` by defaulting to `False` would claim a check that never
happened. Conflating "ran, locally" into NULL would claim the opposite.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.add_column(sa.Column("model", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("model_revision", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("provider", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("host", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("profile_check_skipped", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run_step") as batch_op:
        batch_op.drop_column("profile_check_skipped")
        batch_op.drop_column("host")
        batch_op.drop_column("provider")
        batch_op.drop_column("model_revision")
        batch_op.drop_column("model")
