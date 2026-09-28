"""create speaker_name table

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-25

A name someone gives a diarised speaker (`spk0`, `spk1`) has to
survive the recording being reprocessed, and reprocessing writes a brand
new Transcript with brand new Segment rows. Segment.person_id (migration
0011) cannot be the place that name lives, because there is no Segment
left to carry it the moment a new run starts. This table is the one place
a label's name lives independently of any single Transcript: keyed by
(recording_id, speaker_label), read back by diarization.speaker_names.
reapply_known_speakers the moment a new Transcript's Segments get their
own labels, so "Names apply to this recording and stay attached if it is
re-processed" is true across a rerun, not just within one page load.

`person_id` has no ON DELETE behaviour of its own beyond the database
default: nothing in this package deletes a Person today, so there is no
existing case to decide for.

downgrade() drops the table, taking every name given this way with it,
because a downgrade's data loss should be said, not discovered, same as
migration 0011 says of itself for Person and User.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "speaker_name",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "recording_id",
            sa.String(length=36),
            sa.ForeignKey("recording.id"),
            nullable=False,
        ),
        sa.Column("speaker_label", sa.String(length=32), nullable=False),
        sa.Column("person_id", sa.String(length=36), sa.ForeignKey("person.id"), nullable=False),
        sa.UniqueConstraint(
            "recording_id", "speaker_label", name="uq_speaker_name_recording_label"
        ),
    )


def downgrade() -> None:
    op.drop_table("speaker_name")
