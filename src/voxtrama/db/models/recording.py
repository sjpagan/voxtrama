"""SQLAlchemy model for a Recording: an audio file imported into Voxtrama."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from voxtrama.db.models.run import Base


class Recording(Base):
    """The audio ingest imported, plus the metadata it derived while doing so."""

    __tablename__ = "recording"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename: Mapped[str] = mapped_column(String)
    stored_path: Mapped[str] = mapped_column(String)
    content_sha256: Mapped[str] = mapped_column(String(64))
    duration_seconds: Mapped[float] = mapped_column(Float)
    media_format: Mapped[str] = mapped_column(String)
    imported_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    # Set by ingest.local_file.import_local_file, from a user id the
    # caller resolved and passed in: ingest is core and cannot call
    # db.people.local_user itself. Nullable, no
    # server_default: same reasoning as Run.created_by (see its comment),
    # which follows migration 0010's for `choices`.
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("user.id"), nullable=True)
    # Set by the URL import, since removed: rows
    # imported before keep them readable, new ones leave them NULL. Both
    # nullable, no server_default, same reasoning as created_by
    # above: a Recording imported from a local file has neither, and NULL
    # says "no provenance to report" better than "" would. Two columns, not
    # a single provenance flag: manifest.sections.input_info derives
    # `provenance` from source_url being set, rather than storing the same
    # fact twice where the two could disagree. Named source_title, the same
    # name the manifest publishes it under (ManifestInput.source_title):
    # one name for the one fact, so this column has no second name to drift
    # from. The value comes from FetchedSource.label, but "label" is that
    # interface's own generic name (ingest.source's docstring), not this
    # column's.
    source_title: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
