"""worker.tasks.execute_run_job refuses a Run when the schema is behind head.

A Run already queued when the schema fell behind is the gap this
gate closes: the queue had accepted it before anyone noticed. This
fakes that: a database migrated to head, then its own
alembic_version row rewritten to something older, the same trick
tests/test_runs_api_create_migration_gate.py uses for the API side.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from voxtrama.config.settings import get_settings
from voxtrama.db.models.run import Run, RunState
from voxtrama.worker.tasks import execute_run_job

ALEMBIC_INI = "alembic.ini"


def test_execute_run_job_fails_the_run_when_the_schema_is_behind_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("VOXTRAMA_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("VOXTRAMA_QUEUE_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()
    command.upgrade(Config(ALEMBIC_INI), "head")
    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        session.add(
            Run(
                id="run-behind",
                workflow_name="demo",
                workflow_version="1.0.0",
                state=RunState.PENDING,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = '0009'"))

    execute_run_job("run-behind")

    with Session(engine) as session:
        run = session.get(Run, "run-behind")
        assert run is not None
        assert run.state == RunState.FAILED
        assert run.error_code == "migrations_pending"
        assert run.error == "database is not at Alembic's head revision"
