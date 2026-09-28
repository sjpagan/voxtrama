"""add source_title and source_url to recording

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-22

Two nullable columns, no server_default, for the same reason migration
0010's comment gives for `choices` and 0011's for `created_by`: a
Recording imported before this migration (or imported from a local file,
which has neither a title nor a URL to report) has no provenance to
record, and NULL says that better than an invented empty string would.

`source_title`, not `source_label`: the manifest publishes the same value
under `input.source_title`, and one name for one fact
is the rule `ManifestChoices` already states for itself. `IngestSource`'s
own `label` field (ingest/source.py) keeps its name: that is the
interface's generic term, not this column's.

Nothing here writes the `provenance` a manifest reports: sections.py
derives "url" vs "local_file" from whether `source_url` is set, rather
than a third column that could disagree with these two.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("recording") as batch_op:
        batch_op.add_column(sa.Column("source_title", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("source_url", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("recording") as batch_op:
        batch_op.drop_column("source_url")
        batch_op.drop_column("source_title")
