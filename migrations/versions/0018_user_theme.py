"""add theme to user

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-23

This lets the person choose between light, dark and following the
system. The choice has to survive a restart, and where it is kept is the
decision this migration carries out.

Not `localStorage`: that lives in **a browser**, so the same
installation opened from two of them would show two themes, and clearing
site data would silently forget the choice. It also gives up the three
properties the project defends for configuration: it versions, it copies
between machines, it belongs in an infrastructure repository.

On the user row instead, next to their name: the theme is a preference
**of the person**, not of the browser they happen to be using, and the
database already sits inside the data directory (config.paths)
that copies between machines as a whole. `User.role` is already a
per-user setting on this same row, so this is not a new kind of column.

`server_default="auto"` and NOT NULL: every existing row gets the
default that matches what the product does today: no explicit choice,
system preference decides, dark when there is none.
That is not an invented value standing in for a missing one. It is the
state those installations are in.

The default stays on the column rather than being dropped after the
backfill, unlike migration 0017's two name columns: a row inserted by
the 0011 seed on a fresh database must also get "auto" without the
seed knowing this column exists.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("theme", sa.String(), nullable=False, server_default="auto"))


def downgrade() -> None:
    # Dropping this one loses nothing that cannot be chosen again in a
    # click, unlike 0017's names: there is no value to rebuild on the way
    # back, only a preference that returns to following the system.
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("theme")
