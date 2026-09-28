"""Tests for the `voxtrama correct` command."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

import voxtrama.cli.commands.correct as correct_command
from voxtrama.cli.main import app
from voxtrama.db.models import Base, Recording

runner = CliRunner()


def _seeded_session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(
            Recording(
                id="rec1",
                original_filename="clip.opus",
                stored_path="recordings/rec1/clip.opus",
                content_sha256="0" * 64,
                duration_seconds=10.0,
                media_format="opus",
                source_title="Original title",
                source_url="https://example.com/watch?v=abc",
            )
        )
        session.commit()
    return factory


def test_correct_updates_the_title(monkeypatch) -> None:
    factory = _seeded_session_factory()
    monkeypatch.setattr(correct_command, "build_session_factory", lambda: factory)

    result = runner.invoke(app, ["correct", "rec1", "--label", "The real title"])

    assert result.exit_code == 0
    with factory() as session:
        assert session.get(Recording, "rec1").source_title == "The real title"


def test_correct_with_neither_option_fails_without_touching_the_database(monkeypatch) -> None:
    factory = _seeded_session_factory()
    monkeypatch.setattr(correct_command, "build_session_factory", lambda: factory)

    result = runner.invoke(app, ["correct", "rec1"])

    assert result.exit_code == 1
    with factory() as session:
        assert session.get(Recording, "rec1").source_title == "Original title"


def test_correct_an_unknown_id_fails(monkeypatch) -> None:
    factory = _seeded_session_factory()
    monkeypatch.setattr(correct_command, "build_session_factory", lambda: factory)

    result = runner.invoke(app, ["correct", "does-not-exist", "--label", "x"])

    assert result.exit_code == 1
