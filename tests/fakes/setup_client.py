"""Shared fixtures for the guided setup's web tests: a TestClient
whose machine reading is a hand-built MachineReport, never the real one.

Split from the test modules themselves so test_web_setup_processing.py
and test_web_setup_finish.py both stay under the project's 150-line file cap
without duplicating this setup.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

import voxtrama.api.routes.setup_models as setup_models_route
import voxtrama.api.routes.setup_processing as setup_processing_route
import voxtrama.setup.step_defaults as step_defaults
from fakes.queue import InMemoryQueue
from voxtrama.api.app import create_app
from voxtrama.api.deps import get_db, get_queue
from voxtrama.config.settings import Settings, get_settings
from voxtrama.db.models import Base, User
from voxtrama.db.models.user import ROLE_OWNER
from voxtrama.diagnostics.machine import MachineReport

APPLE_SILICON = MachineReport(
    platform="darwin",
    architecture="arm64",
    cpu_count=16,
    performance_cores=11,
    efficiency_cores=5,
    cpu_brand="Apple M3 Pro",
    total_memory_bytes=36 * 1024**3,
    unified_memory=True,
    free_disk_bytes=500 * 1024**3,
    gpu_available=True,
    accelerator="mps",
    in_container=False,
)


def short_on_space(machine: MachineReport, free_bytes: int) -> MachineReport:
    fields = {f: getattr(machine, f) for f in machine.__dataclass_fields__}
    fields["free_disk_bytes"] = free_bytes
    return MachineReport(**fields)


def build_engine(tmp_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{tmp_path / 'setup.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(given_name="Giorgio", family_name="Pagano", role=ROLE_OWNER))
        session.commit()
    return engine


def build_client(
    engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    queue: InMemoryQueue | None = None,
) -> Iterator[TestClient]:
    """A TestClient whose two heavy machine reads are patched to APPLE_SILICON.

    `queue` defaults to a fresh InMemoryQueue (the download button
    enqueues rather than blocking), passed in when a test wants to
    inspect it afterwards, built here otherwise.
    """
    monkeypatch.setattr(setup_processing_route, "read_machine", lambda _dir: APPLE_SILICON)
    monkeypatch.setattr(setup_models_route, "read_machine", lambda _dir: APPLE_SILICON)
    monkeypatch.setattr(step_defaults, "read_machine", lambda _dir: APPLE_SILICON)

    def _override_get_db() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(data_dir=tmp_path)
    app.dependency_overrides[get_queue] = lambda: queue if queue is not None else InMemoryQueue()
    yield TestClient(app)
