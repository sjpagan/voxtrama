"""SQLAlchemy engine and session factory, built from application settings."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from voxtrama.config.settings import Settings, get_settings


def build_engine(settings: Settings) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(settings.database_url, connect_args=connect_args)


def build_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Create a session factory bound to the configured database."""
    settings = settings or get_settings()
    return sessionmaker(bind=build_engine(settings), expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session, committing on success and rolling back on error."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
