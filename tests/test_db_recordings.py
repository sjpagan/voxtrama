"""Tests for voxtrama.db.recordings.correct_source."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from voxtrama.db.models import Recording
from voxtrama.db.recordings import RecordingNotFoundError, correct_source


def _seed_recording(session: Session, **overrides) -> Recording:
    recording = Recording(
        original_filename="clip.opus",
        stored_path="recordings/rec1/clip.opus",
        content_sha256="0" * 64,
        duration_seconds=10.0,
        media_format="opus",
        source_title="Original title",
        source_url="https://example.com/watch?v=abc",
        **overrides,
    )
    session.add(recording)
    session.commit()
    return recording


def test_correct_source_updates_only_the_title_when_only_title_is_given(
    db_session: Session,
) -> None:
    recording = _seed_recording(db_session)

    corrected = correct_source(db_session, recording.id, source_title="The real title")

    assert corrected.source_title == "The real title"
    assert corrected.source_url == "https://example.com/watch?v=abc"


def test_correct_source_updates_only_the_url_when_only_url_is_given(db_session: Session) -> None:
    recording = _seed_recording(db_session)

    corrected = correct_source(db_session, recording.id, source_url="https://example.com/new")

    assert corrected.source_title == "Original title"
    assert corrected.source_url == "https://example.com/new"


def test_correct_source_updates_both_when_both_are_given(db_session: Session) -> None:
    recording = _seed_recording(db_session)

    corrected = correct_source(
        db_session, recording.id, source_title="New title", source_url="https://example.com/new"
    )

    assert corrected.source_title == "New title"
    assert corrected.source_url == "https://example.com/new"


def test_correct_source_persists(db_session: Session) -> None:
    recording = _seed_recording(db_session)

    correct_source(db_session, recording.id, source_title="New title")

    reread = db_session.get(Recording, recording.id)
    assert reread.source_title == "New title"


def test_correct_source_raises_for_an_unknown_id(db_session: Session) -> None:
    with pytest.raises(RecordingNotFoundError):
        correct_source(db_session, "does-not-exist", source_title="anything")
