"""FastAPI dependency providers: settings, database session, and queue."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.session import build_engine, build_session_factory, session_scope
from voxtrama.queue.base import Queue
from voxtrama.queue.rq_backend import RQBackend


@lru_cache
def get_queue() -> Queue:
    """Build the queue backend from application settings, once per process."""
    return RQBackend(get_settings().queue_url)


@lru_cache
def get_engine() -> Engine:
    """Build the database engine from application settings, once per process."""
    return build_engine(get_settings())


def get_db() -> Iterator[Session]:
    """Yield a database session for the duration of a request."""
    with session_scope(build_session_factory()) as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
QueueDep = Annotated[Queue, Depends(get_queue)]
EngineDep = Annotated[Engine, Depends(get_engine)]
DbDep = Annotated[Session, Depends(get_db)]
