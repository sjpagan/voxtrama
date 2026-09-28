"""create person and user tables, link segment/run/recording to them

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-22

Community Edition has "one [User], created at first
startup". This migration is that first startup, not application code in
`web`: the migration service runs once, before `web` and
`worker` start, so two containers racing to create that row on the same
SQLite file never need a lock between them ("a lock between containers
over a SQLite file is fragile, and the defect it produces is
intermittent"). Running here instead makes the row exist once, visibly,
before anyone could read it. "Owner" is a placeholder renamed at the
guided first run, not decided by this migration.

created_by on run and recording is nullable with no server_default, for
the same reason migration 0010's own comment gives for `choices`: a row
written before this migration has no author, and NULL says that better
than a value invented for every row that came before it.

downgrade() loses data, and that should be said, not
discovered: it drops the `person` table, taking with it every name a
human assigned by hand to a speaker (the reason Person exists). It
drops the `user` table, taking the local user this migration seeds and
whatever a User.person_id link recorded. And it drops the
`created_by` column from both `run` and `recording`, taking the record
of who created them. This is what "downgrade below the point Person and
User existed" has to mean (there is no schema below 0011 for any of
that to live in), but it is not free, and running it says so first.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _create_person_and_user_tables() -> None:
    op.create_table(
        "person",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("given_name", sa.String(), nullable=False),
        sa.Column("family_name", sa.String(), nullable=False),
    )
    op.create_table(
        "user",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("person_id", sa.String(length=36), sa.ForeignKey("person.id"), nullable=True),
    )


def _seed_local_user() -> None:
    # A lightweight sa.table(), not the ORM User: a migration must keep
    # working after db.models.user.User changes shape, so it describes
    # the columns it needs rather than importing the model.
    user_table = sa.table(
        "user",
        sa.column("id", sa.String),
        sa.column("display_name", sa.String),
        sa.column("role", sa.String),
        sa.column("person_id", sa.String),
    )
    op.bulk_insert(
        user_table,
        [{"id": str(uuid.uuid4()), "display_name": "Owner", "role": "owner", "person_id": None}],
    )


def _link_existing_tables() -> None:
    # batch mode: SQLite cannot ALTER TABLE ADD a foreign key directly
    # (see migration 0002's own comment), so Alembic recreates the table.
    with op.batch_alter_table("segment") as batch_op:
        batch_op.create_foreign_key("fk_segment_person_id_person", "person", ["person_id"], ["id"])
    with op.batch_alter_table("run") as batch_op:
        batch_op.add_column(sa.Column("created_by", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key("fk_run_created_by_user", "user", ["created_by"], ["id"])
    with op.batch_alter_table("recording") as batch_op:
        batch_op.add_column(sa.Column("created_by", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key("fk_recording_created_by_user", "user", ["created_by"], ["id"])


def upgrade() -> None:
    _create_person_and_user_tables()
    _seed_local_user()
    _link_existing_tables()


def downgrade() -> None:
    with op.batch_alter_table("recording") as batch_op:
        batch_op.drop_constraint("fk_recording_created_by_user", type_="foreignkey")
        batch_op.drop_column("created_by")
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_constraint("fk_run_created_by_user", type_="foreignkey")
        batch_op.drop_column("created_by")
    with op.batch_alter_table("segment") as batch_op:
        batch_op.drop_constraint("fk_segment_person_id_person", type_="foreignkey")
    op.drop_table("user")
    op.drop_table("person")
