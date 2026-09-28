"""split user.display_name into given_name and family_name

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-23

The local user now has a profile page where the name can finally be
written. Until now it could not be: nothing in `src/` ever wrote
`display_name`: migration 0011 seeded the single row with the literal
`"Owner"` and that was the end of it.

Two columns rather than one, because the row is meant to grow. The
Enterprise edition will put more of a person on it, and a single
composed string would have to be split after the fact to get there,
guessing where a name ends and a family name begins, on data a person
never agreed to have parsed. Two columns ask the question once, to the
person, in a form.

`display_name` is dropped, not kept in step. Keeping a derived copy
would mean two places carrying the same fact and a rule that says only
one of them may be written. This project has watched that discipline
fail six times over (Run.job_id, Evidence, RunState.CANCELLED,
Step.model_override, and the two Settings fields the documentation
still described wrongly). The surface is one reader, `rendering.identity`,
which composes from the two columns instead.

**The transfer is what this migration is for.**
`display_name` is not empty: every existing installation holds `"Owner"`,
seeded by 0011. One word is therefore not the rare case here. It is the
only case that exists in the wild. The rule: everything before the first
space becomes the given name, the remainder becomes the family name, and
a single word leaves the family name empty rather than inventing one.
`"Owner"` becomes given `"Owner"`, family `""`, and the header shows one
letter, which is what rendering.identity's rule already does for
a one-word name.

Empty strings, not NULL, for a name nobody has filled in: the column
says "not written yet" the same way whether it was never asked or
deliberately left blank, and every reader already has to handle the
blank case for the family name of a one-word name.

**Downgrade restores the value, it does not just drop the columns.**
`display_name` is rebuilt by joining the two with a space and trimming,
so going back does not lose what the person wrote. A downgrade that
silently emptied the only piece of identity in the database would be
worse than one that refuses to run.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_user = sa.table(
    "user",
    sa.column("id", sa.String),
    sa.column("display_name", sa.String),
    sa.column("given_name", sa.String),
    sa.column("family_name", sa.String),
)


def _split(display_name: str) -> tuple[str, str]:
    """(given, family) from one stored name: first word, then the rest."""
    given, _, family = display_name.strip().partition(" ")
    return given, family.strip()


def upgrade() -> None:
    # Added nullable so the rows that already exist can be filled in
    # before the column is asked to be NOT NULL. Adding a NOT NULL
    # column to a populated table needs either a server_default that
    # would then have to be dropped, or this order.
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("given_name", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("family_name", sa.String(), nullable=True))

    connection = op.get_bind()
    for row in connection.execute(sa.select(_user.c.id, _user.c.display_name)).fetchall():
        given, family = _split(row.display_name or "")
        connection.execute(
            sa.update(_user)
            .where(_user.c.id == row.id)
            .values(given_name=given, family_name=family)
        )

    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("given_name", nullable=False)
        batch_op.alter_column("family_name", nullable=False)
        batch_op.drop_column("display_name")


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(), nullable=True))

    connection = op.get_bind()
    for row in connection.execute(
        sa.select(_user.c.id, _user.c.given_name, _user.c.family_name)
    ).fetchall():
        rejoined = f"{row.given_name or ''} {row.family_name or ''}".strip()
        connection.execute(
            sa.update(_user).where(_user.c.id == row.id).values(display_name=rejoined)
        )

    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("display_name", nullable=False)
        batch_op.drop_column("family_name")
        batch_op.drop_column("given_name")
